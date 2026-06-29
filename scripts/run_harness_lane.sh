#!/bin/bash
# Self-contained lane runner: ./run_harness_lane.sh "answerer:reader answerer:reader ..."
cd /Users/santoshg/Coding/ClinicalHarness
set -a; . ./.env.local; . ./.env.crossmodel.local; set +a
export SSL_CERT_FILE="$(python3.11 -c 'import certifi; print(certifi.where())')"
export JUDGE_VOTES=3
: "${NCBI_MIN_INTERVAL:=0.5}"   # overridable so extra concurrent lanes can throttle harder
export NCBI_MIN_INTERVAL
MAN="data/eval/crossmodel/flash_fail_postcutoff.jsonl"
for pair in $1; do
  ans="${pair%%:*}"; rdr="${pair##*:}"
  out="data/eval/crossmodel_harness/${ans}__reader_${rdr}"
  echo "=== $(date +%H:%M) START $ans / $rdr ==="
  PYTHONPATH=src python3.11 scripts/crossmodel_harness.py "$ans" "$rdr" "$MAN" "$out" > "${out}.log" 2>&1
  echo "=== $(date +%H:%M) END $ans / $rdr (exit $?) ==="
done
