"""Tests unitarios para spike_cross_encoder.py.

Cubre:
- test_spike_exits_with_missing_dataset — path inexistente → exit 1
- test_spike_generates_output_file_with_synthetic — --synthetic → crea JSON output
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.poc.spike_cross_encoder import main


class TestSpikeExitsWithMissingDataset:
    def test_spike_exits_with_missing_dataset(self, tmp_path: Path):
        """Path inexistente sin --synthetic → exit 1 con mensaje claro."""
        non_existent = tmp_path / "does_not_exist.jsonl"
        exit_code = main(
            [
                "--dataset",
                str(non_existent),
                "--output-dir",
                str(tmp_path / "rnd"),
            ]
        )
        assert exit_code == 1, f"Se esperaba exit code 1 para dataset inexistente, got {exit_code}"

    def test_spike_exits_with_insufficient_dataset(self, tmp_path: Path):
        """Dataset con < 500 pares → exit 1."""
        dataset = tmp_path / "small.jsonl"
        # Escribir solo 10 líneas (< 500 requeridas)
        with open(dataset, "w", encoding="utf-8") as f:
            for i in range(10):
                f.write(
                    json.dumps(
                        {
                            "sku": f"SKU{i}",
                            "query": f"query {i}",
                            "candidates": [f"cand {j}" for j in range(5)],
                            "relevant_index": 0,
                        }
                    )
                    + "\n"
                )
        exit_code = main(
            [
                "--dataset",
                str(dataset),
                "--output-dir",
                str(tmp_path / "rnd"),
            ]
        )
        assert exit_code == 1


class TestSpikeGeneratesOutputFileWithSynthetic:
    def test_spike_generates_output_file_with_synthetic(self, tmp_path: Path):
        """--synthetic → crea docs/rnd/spike-cross-encoder-results-{date}.json."""
        output_dir = tmp_path / "rnd"
        exit_code = main(
            [
                "--synthetic",
                "--candidates",
                "3",
                "--output-dir",
                str(output_dir),
            ]
        )
        # El script debe completar (exit 0)
        assert exit_code == 0, f"Se esperaba exit code 0, got {exit_code}"

        # Debe existir al menos un JSON de resultados
        output_files = list(output_dir.glob("spike-cross-encoder-results-*.json"))
        assert len(output_files) == 1, (
            f"Se esperaba 1 archivo JSON de resultados, encontrados: {output_files}"
        )

        # El JSON debe tener la estructura esperada
        data = json.loads(output_files[0].read_text(encoding="utf-8"))
        assert "run_at" in data, "JSON debe tener clave 'run_at'"
        assert "sample_size" in data, "JSON debe tener clave 'sample_size'"
        assert "cohere" in data, "JSON debe tener clave 'cohere'"
        assert "cross_encoder_local" in data, "JSON debe tener clave 'cross_encoder_local'"

    def test_spike_synthetic_sample_size_correct(self, tmp_path: Path):
        """--synthetic genera exactamente 100 SKUs (MAX_SKUS_SAMPLE)."""
        from scripts.poc.spike_cross_encoder import MAX_SKUS_SAMPLE

        output_dir = tmp_path / "rnd"
        main(
            [
                "--synthetic",
                "--candidates",
                "3",
                "--output-dir",
                str(output_dir),
            ]
        )
        output_files = list(output_dir.glob("spike-cross-encoder-results-*.json"))
        data = json.loads(output_files[0].read_text(encoding="utf-8"))
        assert data["sample_size"] == MAX_SKUS_SAMPLE, (
            f"Se esperaban {MAX_SKUS_SAMPLE} SKUs sintéticos, got {data['sample_size']}"
        )
