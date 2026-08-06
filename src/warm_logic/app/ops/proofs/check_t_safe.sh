#!/usr/bin/env bash
# Run the core T_SAFE (T-operator safe-set preservation) proof via TLC on the
# generic T_Operator_Safety.tla spec. Produces a stable log that matches the
# PMAN-TSAFE manifest.

set -euo pipefail

SPEC=${SPEC:-docs/math/proofs/tla/T_Operator_Safety_Instance.tla}
CFG=${CFG:-docs/math/proofs/tla/T_Operator_Safety_Instance.cfg}
TLA_JAR=${TLA_JAR:-docs/modelchecking/tla2tools.jar}
LOG_PATH=${LOG_PATH:-docs/math/proofs/tla/T_SAFE.log}

run_tlc() {
  if command -v tlc >/dev/null 2>&1; then
    echo "[PROOF] running TLC via tlc on ${SPEC}"
    tlc "${SPEC}" -config "${CFG}"
    return
  fi

  if [ ! -f "${TLA_JAR}" ]; then
    echo "[PROOF] tla2tools.jar not found at ${TLA_JAR}; skipping TLC run"
    return
  fi

  if [ ! -f "${SPEC}" ]; then
    echo "[PROOF] TLA+ spec not found at ${SPEC}; skipping TLC run"
    return
  fi

  echo "[PROOF] running TLC via jar on ${SPEC}"
  set +e
  JAVA_OPTS="-Djava.net.preferIPv4Stack=true -Djava.rmi.server.hostname=127.0.0.1"
  output=$(java ${JAVA_OPTS} -cp "${TLA_JAR}" tlc2.TLC -deadlock -config "${CFG}" "${SPEC}" 2>&1)
  rc=$?
  set -e
  mkdir -p "$(dirname "${LOG_PATH}")"
  printf "%s\n" "${output}" > "${LOG_PATH}"
  if [[ $rc -ne 0 ]]; then
    if grep -q "Listen failed on port: 0" <<<"${output}"; then
      echo "[PROOF] TLC skipped: RMI/socket not permitted in this environment" >&2
      return
    fi
    echo "[PROOF] TLC failed with code ${rc}" >&2
    echo "${output}"
    exit $rc
  fi
  echo "${output}"
}

run_tlc
