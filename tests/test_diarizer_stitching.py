import unittest
import json
import os
import tempfile

from pipeline.diarizer import (WINDOW_CACHE_SCHEMA,
                               _accept_second_speaker_recovery,
                               _embedding_label_map, _global_embedding_maps,
                               _infer_exact_from_shared_features,
                               _load_window_checkpoint, _stitch_label_map)


class DiarizerStitchingTests(unittest.TestCase):
    def test_swapped_local_names_follow_overlap_duration(self):
        prior = [
            {"speaker": "A", "start": 45.0, "end": 50.0},
            {"speaker": "B", "start": 50.0, "end": 60.0},
        ]
        local = [
            {"speaker": "SPEAKER_01", "start": 45.0, "end": 50.0},
            {"speaker": "SPEAKER_00", "start": 50.0, "end": 60.0},
        ]
        mapping = _stitch_label_map(local, prior, ["A", "B"])
        self.assertEqual(mapping, {"SPEAKER_00": "B", "SPEAKER_01": "A"})

    def test_label_missing_from_overlap_gets_remaining_identity(self):
        prior = [{"speaker": "A", "start": 45.0, "end": 60.0}]
        local = [
            {"speaker": "X", "start": 45.0, "end": 60.0},
            {"speaker": "Y", "start": 65.0, "end": 70.0},
        ]
        mapping = _stitch_label_map(local, prior, ["A", "B"])
        self.assertEqual(mapping["X"], "A")
        self.assertEqual(mapping["Y"], "B")

    def test_window_checkpoint_requires_exact_identity(self):
        expected = {"model": "model", "cache_identity": "episode-a"}
        with tempfile.TemporaryDirectory(dir=".") as folder:
            path = os.path.join(folder, "window.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"schema_version": WINDOW_CACHE_SCHEMA, **expected,
                           "turns": [{"speaker": "A", "start": 0, "end": 1}],
                           "speaker_embeddings": {"A": [1.0, 0.0]}}, handle)
            self.assertIsNotNone(_load_window_checkpoint(path, expected))
            self.assertIsNone(_load_window_checkpoint(
                path, {"model": "model", "cache_identity": "episode-b"}))

    def test_voice_embeddings_prevent_temporal_label_swap(self):
        # Local names are arbitrary: X acoustically matches canonical B and Y
        # matches A. The permutation constraint assigns both identities once.
        mapping, diagnostics = _embedding_label_map(
            {"X": [0.0, 1.0], "Y": [1.0, 0.0]},
            {"A": [0.98, 0.02], "B": [0.01, 0.99]},
        )
        self.assertEqual(mapping, {"X": "B", "Y": "A"})
        self.assertGreater(diagnostics["assignment_margin"], 0.9)

    def test_invalid_embedding_count_requests_fallback(self):
        mapping, diagnostics = _embedding_label_map(
            {"X": [1.0, 0.0]}, {"A": [1.0, 0.0], "B": [0.0, 1.0]})
        self.assertIsNone(mapping)
        self.assertEqual(diagnostics["reason"], "embedding-label-count-mismatch")

    def test_global_constrained_clustering_handles_local_name_swaps(self):
        records = [
            {"speaker_embeddings": {"X": [1.0, 0.0], "Y": [0.0, 1.0]},
             "turns": [{"speaker": "X", "start": 0, "end": 10},
                       {"speaker": "Y", "start": 10, "end": 20}]},
            {"speaker_embeddings": {"X": [0.02, 0.98], "Y": [0.99, 0.01]},
             "turns": [{"speaker": "X", "start": 20, "end": 30},
                       {"speaker": "Y", "start": 30, "end": 40}]},
            {"speaker_embeddings": {"X": [0.98, 0.02], "Y": [0.01, 0.99]},
             "turns": [{"speaker": "X", "start": 40, "end": 50},
                       {"speaker": "Y", "start": 50, "end": 60}]},
        ]
        maps, diagnostics = _global_embedding_maps(records)
        self.assertEqual(maps[0]["X"], "PODCAST_SPEAKER_00")
        self.assertEqual(maps[1]["Y"], "PODCAST_SPEAKER_00")
        self.assertEqual(maps[2]["X"], "PODCAST_SPEAKER_00")
        self.assertEqual(diagnostics["valid_windows"], 3)
        self.assertGreater(diagnostics["assignment_margin_minimum"], 0.9)

    def test_global_clustering_assigns_true_single_speaker_window(self):
        records = [
            {"speaker_embeddings": {"A": [1.0, 0.0], "B": [0.0, 1.0]},
             "turns": [{"speaker": "A", "start": 0, "end": 10},
                       {"speaker": "B", "start": 10, "end": 20}]},
            {"speaker_embeddings": {"LOCAL": [0.99, 0.01]},
             "turns": [{"speaker": "LOCAL", "start": 20, "end": 40}]},
        ]
        maps, diagnostics = _global_embedding_maps(records)
        self.assertEqual(maps[1]["LOCAL"], "PODCAST_SPEAKER_00")
        self.assertEqual(diagnostics["single_speaker_windows"], 1)

    def test_distinct_forced_embeddings_recover_brief_second_speaker(self):
        accepted, cosine = _accept_second_speaker_recovery(
            {"ONLY": [1.0, 0.0]},
            {"FIRST": [1.0, 0.0], "SECOND": [0.3, 0.954]})
        self.assertTrue(accepted)
        self.assertLess(cosine, 0.7)

    def test_similar_forced_embeddings_remain_monologue(self):
        accepted, cosine = _accept_second_speaker_recovery(
            {"ONLY": [1.0, 0.0]},
            {"SPLIT_A": [1.0, 0.0], "SPLIT_B": [0.95, 0.1]})
        self.assertFalse(accepted)
        self.assertGreater(cosine, 0.7)

    def test_exact_reclustering_reuses_and_then_restores_front_end(self):
        class FakePipeline:
            def get_segmentations(self, file, hook=None):
                return "expensive-segmentation"

            def get_embeddings(self, file, segmentations, exclude_overlap=False, hook=None):
                return "expensive-embeddings"

            def __call__(self, audio, **kwargs):
                return (self.get_segmentations(audio),
                        self.get_embeddings(audio, None), kwargs["num_speakers"])

        pipeline = FakePipeline()
        original_segmentations = pipeline.get_segmentations
        original_embeddings = pipeline.get_embeddings
        result = _infer_exact_from_shared_features(
            pipeline, "waveform", 16000, 2,
            {"segmentation": "shared-segmentation", "embeddings": "shared-embeddings"})
        self.assertEqual(result, ("shared-segmentation", "shared-embeddings", 2))
        self.assertEqual(pipeline.get_segmentations("audio"), "expensive-segmentation")
        self.assertEqual(pipeline.get_embeddings("audio", None), "expensive-embeddings")
        self.assertEqual(pipeline.get_segmentations, original_segmentations)
        self.assertEqual(pipeline.get_embeddings, original_embeddings)


if __name__ == "__main__":
    unittest.main()
