"""Génère un CSV simulé au format d'export Tally. Usage : python -m scripts.make_csv 165 > simule.csv"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.core import synthetic as S  # noqa: E402
from app.core.plan import get_codebook  # noqa: E402

n = int(sys.argv[1]) if len(sys.argv) > 1 else 165
sys.stdout.write(S.to_csv_text(S.generate(n, seed=7), get_codebook()))
