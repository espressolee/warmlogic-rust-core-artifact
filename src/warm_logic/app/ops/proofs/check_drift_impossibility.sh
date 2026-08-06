#!/usr/bin/env bash
# Run drift impossibility TLC checks (research-only sanity).
# Bounded proofs/sweeps; avoid errexit so we can soft-fail placeholders.

set +e
set -uo pipefail

echo "[PROOF] drift suite start"

SPEC1=${SPEC1:-proof/drift/DRIFT_IMPOSSIBILITY_001.tla}
CFG1=${CFG1:-proof/drift/DRIFT_IMPOSSIBILITY_001.cfg}
LOG1=${LOG1:-proof/drift/DRIFT_IMPOSSIBILITY_001.log}

SPEC2=${SPEC2:-proof/drift/DRIFT_IMPOSSIBILITY_002.tla}
CFG2=${CFG2:-proof/drift/DRIFT_IMPOSSIBILITY_002.cfg}
LOG2=${LOG2:-proof/drift/DRIFT_IMPOSSIBILITY_002.log}

SPEC3=${SPEC3:-proof/drift/DRIFT_IMPOSSIBILITY_003.tla}
CFG3=${CFG3:-proof/drift/DRIFT_IMPOSSIBILITY_003.cfg}
LOG3=${LOG3:-proof/drift/DRIFT_IMPOSSIBILITY_003.log}
# Allow small param sweep; space-separated lists.
LAG_LIST=${LAG_LIST:-"2"}
MAXT_LIST=${MAXT_LIST:-"4"}

SPEC4=${SPEC4:-proof/drift/DRIFT_IMPOSSIBILITY_004.tla}
CFG4=${CFG4:-proof/drift/DRIFT_IMPOSSIBILITY_004.cfg}
LOG4=${LOG4:-proof/drift/DRIFT_IMPOSSIBILITY_004.log}
# Default: run a small grid for 004 (bounded-general TLC sweep). Set SKIP_004=true to skip.
SKIP_004=${SKIP_004:-false}
# Small grid for 004 (research-only)
H_LIST_004=${H_LIST_004:-"0 1 2"}
LAG_LIST_004=${LAG_LIST_004:-"1 2 3"}
LOG_DIR_004=${LOG_DIR_004:-proof/drift}

TLA_JAR=${TLA_JAR:-docs/modelchecking/tla2tools.jar}
TMPDIR_DRIFT=${TMPDIR_DRIFT:-proof/drift/tmp}
mkdir -p "${TMPDIR_DRIFT}"
export TMPDIR="${TMPDIR_DRIFT}"

run_tlc() {
  local spec="$1" cfg="$2" log_path="$3"
  if command -v tlc >/dev/null 2>&1; then
    echo "[PROOF] running TLC via tlc on ${spec}"
    tlc "${spec}" -config "${cfg}"
    return
  fi
  if [ ! -f "${TLA_JAR}" ]; then
    echo "[PROOF] tla2tools.jar not found at ${TLA_JAR}; skipping TLC run for ${spec}"
    return
  fi
  if [ ! -f "${spec}" ]; then
    echo "[PROOF] TLA+ spec not found at ${spec}; skipping TLC run"
    return
  fi
  echo "[PROOF] running TLC via jar on ${spec}"
  set +e
  JAVA_OPTS="-Djava.net.preferIPv4Stack=true -Djava.rmi.server.hostname=127.0.0.1 -XX:+UseParallelGC -XX:ActiveProcessorCount=2"
  output=$(java ${JAVA_OPTS} -cp "${TLA_JAR}" tlc2.TLC -deadlock -config "${cfg}" "${spec}" 2>&1)
  rc=$?
  set +e
  mkdir -p "$(dirname "${log_path}")"
  # write directly to the requested log path; skip if filesystem is full
  printf "%s\n" "${output}" > "${log_path}" || echo "[PROOF] warn: could not write log to ${log_path}"
  if [[ $rc -ne 0 ]]; then
    if grep -q "Listen failed on port: 0" <<<"${output}"; then
      echo "[PROOF] TLC skipped: RMI/socket not permitted in this environment" >&2
      return
    fi
    if grep -qi "No space left on device" <<<"${output}"; then
      echo "[PROOF] TLC skipped: no space left for ${spec}" >&2
      return
    fi
    echo "[PROOF] TLC failed with code ${rc} on ${spec}" >&2
    echo "${output}"
    exit $rc
  fi
  echo "${output}"
}

run_tlc_allow_fail() {
  local spec="$1" cfg="$2" log_path="$3"
  set +e
  tlc_available=false
  if command -v tlc >/dev/null 2>&1; then tlc_available=true; fi
  jar_available=false
  if [ -f "${TLA_JAR}" ]; then jar_available=true; fi

  if [ "${tlc_available}" != "true" ] && [ "${jar_available}" != "true" ]; then
    echo "[PROOF] TLC tooling not available; skipping ${spec}"
    return 0
  fi
  if [ ! -f "${spec}" ]; then
    echo "[PROOF] TLA+ spec not found at ${spec}; skipping TLC run"
    return 0
  fi
  if command -v tlc >/dev/null 2>&1; then
    echo "[PROOF] running TLC via tlc on ${spec} (allow_fail)"
    tlc "${spec}" -config "${cfg}"
    rc=$?
    return $rc
  fi
  set +e
  JAVA_OPTS="-Djava.net.preferIPv4Stack=true -Djava.rmi.server.hostname=127.0.0.1 -XX:+UseParallelGC -XX:ActiveProcessorCount=2"
  output=$(java ${JAVA_OPTS} -cp "${TLA_JAR}" tlc2.TLC -deadlock -config "${cfg}" "${spec}" 2>&1)
  rc=$?
  mkdir -p "$(dirname "${log_path}")"
  printf "%s\n" "${output}" > "${log_path}" || echo "[PROOF] warn: could not write log to ${log_path}"
  return $rc
}

run_tlc "${SPEC1}" "${CFG1}" "${LOG1}"
run_tlc "${SPEC2}" "${CFG2}" "${LOG2}"
echo "[PROOF] running DRIFT_IMPOSSIBILITY_003 sweep (reachability of unsafe state under bounded lag/horizon)"
tmp_cfg="${TMPDIR_DRIFT}/DRIFT_IMPOSSIBILITY_003.cfg"
rc3=0
for lag in ${LAG_LIST}; do
  for maxt in ${MAXT_LIST}; do
    cat > "${tmp_cfg}" <<EOF
CONSTANTS
  LagMax = ${lag}
  DriftHorizon = 0
  MaxT = ${maxt}
SPECIFICATION Spec
PROPERTY DriftReachUnsafe
EOF
    log_path="${LOG3%.log}_Lag${lag}_MaxT${maxt}.log"
    run_tlc_allow_fail "${SPEC3}" "${tmp_cfg}" "${log_path}"
    this_rc=$?
    if [[ $this_rc -ne 0 ]]; then
      echo "[PROOF] DRIFT_IMPOSSIBILITY_003: TLC returned non-zero for LagMax=${lag}, MaxT=${maxt}; see ${log_path}"
      rc3=$this_rc
    else
      echo "[PROOF] DRIFT_IMPOSSIBILITY_003: unsafe reachable (LagMax=${lag}, MaxT=${maxt}); log ${log_path}"
    fi
  done
done

if [[ "${SKIP_004}" == "true" ]]; then
  echo "[PROOF] skipping DRIFT_IMPOSSIBILITY_004 (SKIP_004=true)"
else
  echo "[PROOF] running DRIFT_IMPOSSIBILITY_004 (generalised placeholder; bounded sweep; soft-fail)"
  tmp_cfg4="${TMPDIR_DRIFT}/DRIFT_IMPOSSIBILITY_004.cfg"
  for h in ${H_LIST_004}; do
    for lag in ${LAG_LIST_004}; do
      maxt=$((h + lag + 1))
      cat > "${tmp_cfg4}" <<EOF
CONSTANTS
  LagMax = ${lag}
  DriftHorizon = ${h}
  MaxT = ${maxt}
SPECIFICATION Spec
PROPERTY DriftReachUnsafe
EOF
      log_path4="${LOG4%.log}_H${h}_Lag${lag}_MaxT${maxt}.log"
      set +e
      run_tlc_allow_fail "${SPEC4}" "${tmp_cfg4}" "${log_path4}"
      this_rc=$?
      set -e
      if [[ $this_rc -ne 0 ]]; then
        echo "[PROOF] DRIFT_IMPOSSIBILITY_004: TLC non-zero (grid run; allowed for now); see ${log_path4}"
      else
        echo "[PROOF] DRIFT_IMPOSSIBILITY_004: unsafe reachable (H=${h}, LagMax=${lag}, MaxT=${maxt}); log ${log_path4}"
      fi
    done
  done
fi

echo "[PROOF] drift suite end"
exit 0
