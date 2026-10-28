# 설치와 실행

모든 Python 명령은 `python/` 폴더에서 실행합니다.

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

## 벤치마크

```bash
python -m suphago.bench --agent random --games 30 --workers 10
python -m suphago.bench --agent typematch --games 30 --workers 10
python -m suphago.bench --agent mc --plies 1 --games 30 --workers 10 --out mc1.jsonl
python -m suphago.bench --agent mc --plies 2 --games 30 --workers 10 --out mc2.jsonl
python -m suphago.bench --agent value --model ../runs/value_h30.pt --risk 1 --games 30 --workers 10
```

| 옵션 | 뜻 |
|---|---|
| `--workers` | 동시에 두는 판 수. CPU 코어 수에 맞춤 |
| `--hz` | 60 또는 120. 다음 낙하까지 프레임 수가 달라짐 (기본 60) |
| `--seed` | 첫 게임 시드 (기본 0) |
| `--plies` | 몬테카를로가 볼 수 (1 또는 2) |
| `--n` | 후보 수 (기본 50) |
| `--model` | 가치망 파일 |
| `--risk` | 게임오버 확률 1당 1000점 감점 |
| `--blend` | 몬테카를로 채점 공식 1점당 가산 점수 |

## 기보 수집과 학습

```bash
python -m suphago.collect --agent mc --plies 1 --games 100 --workers 10 --out ../data/mc1
python -m suphago.train_value --data ../data/mc1 --epochs 15 --loader-workers 8 --out ../runs/value_mc1.pt
python -m suphago.train_value --data ../data/mc1 ../data/mc2 --horizon 30 --over-head --epochs 15 --loader-workers 8 --out ../runs/value_h30_all.pt
```

- 같은 폴더에 다시 수집할 땐 `--seed 100100`처럼 시작 번호를 바꿔야 판이 중복되지 않습니다.
- 학습 진행은 `tail -f train_*.log`로 봅니다. `val_mae`가 낮을수록 좋습니다.

## 리플레이

```bash
python -m suphago.replay --agent mc --plies 2 --seed 0 --out ../replays/mc2_seed0.json
cd .. && python -m http.server 8000   # http://localhost:8000/viewer/
```

## 실제 사이트

```bash
python -m suphago.live --agent mc --seed 0 --log live_mc1_seed0.json
python -m suphago.live --agent value --model ../runs/value_h30.pt --risk 1 --seed 0 --log live_value.json
```

창이 뜨면 팝업을 닫고 터미널에서 Enter를 누릅니다. 플레이 중에는 창 위에서 마우스를 움직이지 않습니다.

## 맥에서 밤새 돌리기

```bash
caffeinate -i sh -c '명령1 > a.log 2>&1 ; 명령2 > b.log 2>&1'
```

- `caffeinate`는 가만히 둬서 잠드는 것만 막습니다. 뚜껑을 닫으면 잠들어서 작업이 멈춥니다.
- `;`로 이으면 앞 명령이 실패해도 다음 명령이 돕니다.

## Google Cloud

준비 (한 번만):
```bash
brew install --cask google-cloud-sdk
gcloud auth login
gcloud config set project 프로젝트ID   # gcloud projects list 로 확인
```

실행:
```bash
bash cloud/run.sh start    # 서버 생성, 업로드, 설치, cloud/jobs.sh 시작
bash cloud/run.sh status   # 진행 확인 (TERMINATED면 끝남)
bash cloud/run.sh fetch    # 결과 내려받기 (기보는 data/ 로 복사)
bash cloud/run.sh delete   # 서버 삭제
```

| 환경 변수 | 뜻 |
|---|---|
| `SUPHAGO_MACHINE` | 서버 종류. 여러 개를 공백으로 주면 순서대로 시도 (기본 `c2d-highcpu-32`) |
| `SUPHAGO_SPOT=1` | 스팟 서버 (약 1/3 가격, 중간에 회수될 수 있음) |
| `SUPHAGO_ZONES` | 시도할 존 목록 (기본 서울 a, b, c) |

- 프로젝트 전체 vCPU 한도(`CPUS_ALL_REGIONS`)가 12면 `SUPHAGO_MACHINE="n2-custom-12-12288 e2-custom-12-12288"`처럼 12 vCPU 서버를 씁니다. n2d는 직접 크기를 정할 때 2, 4, 8, 16의 배수만 됩니다.
- 한도 증설은 콘솔에서 안 되는 경우가 있어서 gcloud로 신청합니다:
  ```bash
  gcloud components install beta
  gcloud beta quotas preferences create --service=compute.googleapis.com \
    --quota-id=CPUS-ALL-REGIONS-per-project --preferred-value=64 \
    --project=$(gcloud config get-value project) --email=이메일 --justification="사유"
  ```
- 무료 체험 계정은 GPU를 쓸 수 없습니다. 학습은 맥(MPS)에서 합니다.
- 꺼진 서버도 디스크 요금이 나오니 결과를 받은 뒤 꼭 `delete`합니다.
- 돌릴 작업은 `cloud/jobs.sh`에서 고칩니다.
