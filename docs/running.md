# 설치와 실행

Python 명령은 `python/` 폴더에서, `cloud/` 스크립트는 레포 루트에서 실행합니다.

## 설치

```bash
git clone https://github.com/jiwonsudo/supha-go && cd supha-go
python3.12 -m venv .venv && source .venv/bin/activate
cd engine && npm ci && cd ..
pip install -r python/requirements.txt
```

실제 사이트 플레이까지 하려면:
```bash
pip install playwright && python -m playwright install chromium
```

엔진을 고친 뒤에는 `node engine/test/golden.js`로 해시가 그대로인지 확인합니다. 바뀌었으면 게임 결과가 바뀐 것입니다.

## 벤치마크

```bash
python -m suphago.bench --agent mc --plies 2 --games 30 --workers 10 --out mc2.jsonl
python -m suphago.bench --agent mcv --model ../runs/value_v3.pt --alpha 1 --risk 1 --games 30 --workers 10
python -m suphago.bench --agent ps --policy ../runs/policy_v1.pt --model ../runs/value_v3.pt --alpha 1 --risk 1 --games 30 --workers 10
```

| 옵션 | 뜻 |
|---|---|
| `--agent` | `random`, `typematch`, `mc`, `value`, `mcv`, `ps` |
| `--games`, `--seed` | 판 수, 첫 시드 (기본 0). 같은 시드는 같은 과일 순서 |
| `--workers` | 동시에 두는 판 수. CPU 코어 수에 맞춤 |
| `--hz` | 60 또는 120 (기본 60) |
| `--n`, `--plies`, `--s2` | 후보 수, 1수/2수, 2수에서 둘째 수 샘플 수 |
| `--pair`, `--wm` | 큰 과일 보너스 가중치 |
| `--model` | 가치망 (`value`, `mcv`, `ps`) |
| `--alpha`, `--risk` | 가치망 예상 점수 가중치, 게임오버 벌점 |
| `--blend` | `value`: 공식을 섞는 비율 |
| `--policy`, `--k1`, `--k2` | `ps`: 정책망, 첫 수 후보 수, 둘째 수 후보 수 |
| `--out` | 판별 결과를 jsonl로 추가 저장 |

여러 MC 설정을 같은 시드로 한 번에 돌리려면 `sweep`을 씁니다. 중간에 끊겨도 다시 실행하면 끝난 판은 건너뜁니다.
```bash
python -m suphago.sweep --configs 1:25:1 1:100:1 2:50:3 --seeds 0 49 --workers 10 --out sweep.jsonl
```
설정은 `수:후보 수:둘째 수 샘플`입니다.

## 기보 수집과 학습

```bash
# 기보 (같은 폴더에 다시 모을 땐 --seed를 바꿔 판이 겹치지 않게)
python -m suphago.collect --agent mc --plies 2 --games 100 --workers 10 --out ../data/mc2
python -m suphago.collect --agent mcv --model ../runs/value_v3.pt --alpha 1 --risk 1 --games 200 --seed 200000 --workers 10 --out ../data/sp1
# 분기 기보 (나쁜 수 뒤의 판). --resume이면 이미 모은 것은 건너뜀
python -m suphago.collect_branch --data ../data/mc1 ../data/mc2 --branches 800 --length 40 --workers 10 --out ../data/branch

# 가치망
python -m suphago.train_value --data ../data/mc1 ../data/mc2 ../data/branch --horizon 30 --over-head \
  --epochs 15 --dropout 0.2 --wd 0.01 --loader-workers 8 --out ../runs/value_v3.pt
# 정책망
python -m suphago.train_policy --data ../data/mc1 ../data/mc2 --epochs 10 --loader-workers 8 --out ../runs/policy_v1.pt
```

- 학습 진행은 `tail -f 로그파일`로 봅니다. 한 줄이 한 에폭입니다.
- 가치망은 `val_mae`(낮을수록 좋음), `val_corr`(순위가 맞는 정도), `val_branch_mae`(나쁜 수 뒤의 판)를 봅니다.
- 정책망은 `val_recall10`(정답 칸이 상위 10칸 안에 든 비율)을 봅니다.
- 맥이면 학습은 GPU(MPS), 벤치와 수집은 CPU를 씁니다.

## 분석

```bash
python -m suphago.analyze --data ../data/mc1 ../data/mc2
python -m suphago.feature_study --data ../data/mc1 ../data/mc2 --branch ../data/branch
```

## 리플레이

```bash
python -m suphago.replay --agent mc --plies 2 --seed 0 --out ../replays/mc2_seed0.json
cd .. && python3 -m http.server 8000   # 브라우저에서 http://localhost:8000/viewer/
```

엔진과 에이전트가 시드로 정해져서, 같은 설정과 시드면 벤치와 똑같은 판이 나옵니다. 가치망을 쓰는 에이전트는 신경망 계산이 컴퓨터마다 마지막 자리가 달라, 다른 컴퓨터에서는 판이 달라질 수 있습니다.

## 실제 사이트

```bash
python -m suphago.live --agent mc --plies 2 --seed 0 --log live_mc2_seed0.json
python -m suphago.live --agent mcv --model ../runs/value_v3.pt --alpha 1 --risk 1 --seed 0 --log live_mcv.json
```

창이 뜨면 팝업을 닫고 터미널에서 Enter를 누릅니다. 플레이 중에는 창 위에서 마우스를 움직이지 않습니다.

## 맥에서 오래 돌리기

```bash
caffeinate -i nohup bash 스크립트.sh > 로그.log 2>&1 &
```

- 터미널을 닫아도 계속 돕니다. 뚜껑을 닫거나 전원이 빠지면 잠들어서 멈춥니다.
- 시작하기 전에 `pgrep -fl 스크립트이름`으로 이미 돌고 있는 게 없는지 확인합니다. 같은 작업이 두 개 돌면 시간이 두 배 걸립니다.
- 레포 루트의 `.venv`는 스크립트가 알아서 켭니다.

## Google Cloud

**준비 (한 번만)**
```bash
brew install --cask google-cloud-sdk
gcloud auth login
gcloud config set project supha-go
gcloud components install beta
```

**실행**
```bash
SUPHAGO_MACHINE="n2-highcpu-64 c2d-highcpu-56 n2-highcpu-48" \
SUPHAGO_JOBS=cloud/jobs_sweep_all.sh bash cloud/run.sh start   # 서버 생성, 업로드, 설치, 작업 시작
bash cloud/run.sh status   # 상태와 각 로그의 진행 (TERMINATED면 끝남)
bash cloud/run.sh logs     # 로그 실시간 보기 (Ctrl+C로 나가도 작업은 계속)
bash cloud/run.sh fetch    # 결과 내려받기 → cloud/results-날짜/ (기보는 data/에도 복사)
bash cloud/run.sh delete   # 서버 삭제 (꺼진 서버도 디스크 요금이 나옴)
```

| 환경 변수 | 뜻 |
|---|---|
| `SUPHAGO_JOBS` | 서버에서 돌릴 작업 스크립트 (`start`에 필수). 지난 작업은 `cloud/history/` |
| `SUPHAGO_MACHINE` | 서버 종류. 여러 개를 공백으로 주면 순서대로 시도 |
| `SUPHAGO_DATA` | 같이 올릴 `data/` 폴더 (예: `"mc1 mc2 branch"`) |
| `SUPHAGO_SPOT=1` | 스팟 서버 (약 1/3 가격, 중간에 회수될 수 있음) |
| `SUPHAGO_ZONES` | 시도할 존 목록 (기본 서울 a, b, c) |

- `runs/`의 모델은 항상 같이 올라갑니다.
- 작업 스크립트는 끝나면 `sudo shutdown -h now`로 서버를 끕니다. 새 작업은 `cloud/jobs_sweep_all.sh`를 본떠 만듭니다.
- 클라우드 vCPU 하나는 맥 워커의 약 1/4 속도입니다(M5 기준). 64 vCPU는 맥 1.6대쯤입니다.

**할당량**
- 프로젝트 전체 vCPU 한도는 64입니다(10-28 승인). 256 요청은 거절됐고, 증설 요청은 하루 횟수 제한이 있습니다.
- 한도 증설은 콘솔에서 안 될 때 gcloud로 합니다:
  ```bash
  gcloud beta quotas preferences update fc905c59-4967-4190-a5ab-7d39356c7a01 \
    --service=compute.googleapis.com --project=supha-go \
    --quota-id=CPUS-ALL-REGIONS-per-project --preferred-value=128 \
    --email=failr43@gmail.com --justification="사유"
  gcloud beta quotas preferences list --project=supha-go   # grantedValue 확인
  ```
- 리전 한도는 따로 있습니다: `gcloud compute regions describe asia-northeast3 --format="table(quotas.metric,quotas.limit)" | grep CPUS`
- n2d를 직접 크기 정할 때는 vCPU 2, 4, 8, 16의 배수만 됩니다.
- 무료 체험 계정은 GPU를 쓸 수 없습니다. 학습은 맥에서 합니다.
