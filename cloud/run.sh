#!/usr/bin/env bash
# Run benchmarks and game collection on a Google Cloud spot VM, from your Mac.
#
#   bash cloud/run.sh start      create the VM, upload the code and models, start the jobs
#   bash cloud/run.sh status     show progress
#   bash cloud/run.sh fetch      download results (starts the VM again if it shut itself down)
#   bash cloud/run.sh delete     delete the VM (do this when you are done; a stopped VM still bills its disk)
#
# The jobs to run are in cloud/jobs.sh. When they finish, the VM shuts itself down so
# it stops billing CPU time. Needs gcloud logged in with a project set.
set -euo pipefail

NAME="${SUPHAGO_VM:-suphago-worker}"
MACHINE="${SUPHAGO_MACHINE:-c2d-highcpu-32}"
ZONES="${SUPHAGO_ZONES:-asia-northeast3-a asia-northeast3-b asia-northeast3-c}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
STATE="$ROOT/cloud/.zone"

zone() { cat "$STATE"; }
ssh_vm() { gcloud compute ssh "$NAME" --zone "$(zone)" --quiet --command "$1"; }

cmd_start() {
  [ -n "$(gcloud config get-value project 2>/dev/null)" ] || { echo "gcloud config set project 프로젝트ID 를 먼저 실행하세요."; exit 1; }
  [ -f "$ROOT/runs/value_mc1.pt" ] || { echo "runs/value_mc1.pt 가 없습니다."; exit 1; }
  [ -f "$ROOT/runs/value_h30.pt" ] || { echo "runs/value_h30.pt 가 없습니다. 맥에서 학습이 끝난 뒤 실행하세요."; exit 1; }

  gcloud services enable compute.googleapis.com --quiet
  local created=""
  for z in $ZONES; do
    echo "서버 만드는 중: $MACHINE (스팟) / $z"
    if gcloud compute instances create "$NAME" --zone "$z" --machine-type "$MACHINE" \
        --provisioning-model SPOT --instance-termination-action STOP \
        --image-family ubuntu-2404-lts-amd64 --image-project ubuntu-os-cloud \
        --boot-disk-size 30GB --boot-disk-type pd-balanced --quiet; then
      echo "$z" > "$STATE"; created=1; break
    fi
    echo "  $z 에 자리가 없거나 실패했습니다. 다음 존을 시도합니다."
  done
  [ -n "$created" ] || { echo "서버를 만들지 못했습니다."; exit 1; }

  echo "SSH 준비 기다리는 중..."
  for i in $(seq 1 30); do ssh_vm "true" >/dev/null 2>&1 && break; sleep 10; done

  echo "코드와 모델 올리는 중..."
  local tgz; tgz="$(mktemp -t suphago).tgz"
  COPYFILE_DISABLE=1 tar -C "$ROOT" --exclude engine/node_modules --exclude data --exclude .venv --exclude .git \
      --exclude 'replays/*.json' -czf "$tgz" .
  gcloud compute scp "$tgz" "$NAME:~/suphago.tgz" --zone "$(zone)" --quiet
  rm -f "$tgz"

  echo "설치하고 작업 시작..."
  ssh_vm 'set -e
    mkdir -p ~/supha-go && tar -xzf ~/suphago.tgz -C ~/supha-go
    sudo apt-get update -qq && sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq nodejs npm python3-pip >/dev/null
    cd ~/supha-go/engine && npm ci --silent
    pip3 install --break-system-packages -q numpy
    pip3 install --break-system-packages -q torch --index-url https://download.pytorch.org/whl/cpu
    node test/golden.js
    cd ~/supha-go && nohup bash cloud/jobs.sh > ~/jobs.log 2>&1 < /dev/null &
    sleep 2; echo started'
  echo
  echo "시작했습니다. 진행 확인: bash cloud/run.sh status"
  echo "작업이 끝나면 서버가 스스로 꺼집니다. 아침에 bash cloud/run.sh fetch 후 delete 하세요."
}

cmd_status() {
  gcloud compute instances describe "$NAME" --zone "$(zone)" --format 'value(status)'
  ssh_vm 'tail -n 15 ~/jobs.log; echo; for f in ~/supha-go/python/*.log; do echo "== $(basename $f): $(grep -c "^{" $f 2>/dev/null) 판 완료"; tail -n 1 $f; done' || true
}

cmd_fetch() {
  if [ "$(gcloud compute instances describe "$NAME" --zone "$(zone)" --format 'value(status)')" != "RUNNING" ]; then
    echo "서버 켜는 중 (결과를 받기 위해)..."
    gcloud compute instances start "$NAME" --zone "$(zone)" --quiet
    for i in $(seq 1 30); do ssh_vm "true" >/dev/null 2>&1 && break; sleep 10; done
  fi
  local out="$ROOT/cloud/results-$(date +%Y%m%d-%H%M)"
  mkdir -p "$out"
  ssh_vm 'cd ~/supha-go && tar -czf ~/results.tgz jobs.done python/*.log python/*.jsonl data 2>/dev/null; cp ~/jobs.log ~/supha-go/ 2>/dev/null; true'
  gcloud compute scp "$NAME:~/results.tgz" "$out/" --zone "$(zone)" --quiet
  gcloud compute scp "$NAME:~/jobs.log" "$out/" --zone "$(zone)" --quiet || true
  tar -xzf "$out/results.tgz" -C "$out" && rm "$out/results.tgz"
  if [ -d "$out/data" ]; then mkdir -p "$ROOT/data" && cp -R "$out/data/." "$ROOT/data/"; fi
  echo "받은 위치: $out (기보는 data/ 에도 복사했습니다)"
  echo "다 받았으면: bash cloud/run.sh delete"
}

cmd_delete() {
  gcloud compute instances delete "$NAME" --zone "$(zone)" --quiet
  rm -f "$STATE"
  echo "서버를 삭제했습니다."
}

case "${1:-}" in
  start) cmd_start ;;
  status) cmd_status ;;
  fetch) cmd_fetch ;;
  delete) cmd_delete ;;
  *) sed -n '2,10p' "$0"; exit 1 ;;
esac
