# 전체 구조

## 한눈에 보기

```
┌──────────────────────── 엔진 (Node.js) ────────────────────────┐
│ engine/src/suika.js   게임 규칙 + 물리 (Matter.js 0.19.0)       │
│ engine/src/server.js  명령을 받아 게임을 돌려주는 워커          │
└───────────────▲──────────────────────────────────────────────┘
                │ JSON 한 줄씩 주고받기 (stdin/stdout)
┌───────────────┴────────── Python (python/suphago) ─────────────┐
│ bridge.py   워커 실행, 명령 보내기                              │
│ agents.py   랜덤 / 타입매칭 / 몬테카를로                         │
│ encode.py → model.py → train_value.py / train_policy.py (학습)  │
│ value_agent.py (value, mcv) │ search_agent.py (ps)   (AI 에이전트)│
│ collect.py, collect_branch.py 기보 │ bench.py, sweep.py 벤치     │
│ analyze.py, feature_study.py 분석 │ replay.py │ live.py (실제)   │
└────────────────────────────────────────────────────────────────┘
  viewer/   리플레이 뷰어 (웹)      cloud/   Google Cloud 실행 스크립트
```

## 왜 이렇게 나눴나

- **물리는 JavaScript**: 원본 게임이 Phaser 3.70.0 안의 Matter.js로 돕니다. 다른 물리 엔진(pymunk 등)으로는 같은 값을 넣어도 움직임이 같아지지 않아서, 원본과 같은 엔진을 Node에서 화면 없이 돌립니다.
- **머신러닝은 Python**: PyTorch와 데이터 처리 도구가 Python에 있습니다.
- **둘 사이는 프로세스 통신**: Python이 Node 워커를 서브프로세스로 띄우고, 명령을 JSON 한 줄로 보내 결과를 한 줄로 받습니다. 구조가 단순하고, 워커 수만큼 병렬로 돌리기 쉽습니다.

## 파일별 역할

### engine/

| 파일 | 역할 |
|---|---|
| `src/suika.js` | 게임 엔진. `SuikaGame` 클래스 (`stepFrame`, `drop`, `turn`, `clone`, `fromState`, `state`) |
| `src/server.js` | 워커. 명령: `info`, `new`, `state`, `turn`, `clone`, `free`, `freeMany`, `evaluate`(후보를 굴려 채점용 수치, 2수, 끝 판), `expand`(다음 수 시점까지), `children`(다음 수 시점의 정확한 복사본을 새 게임으로), `turnRecorded`, `load`, `run` |
| `test/compare_ref.js` | 원본 페이지에서 녹화한 24수와 비교 |
| `test/golden.js` | 4판 전체 상태 해시. 엔진 수정 후 값이 바뀌면 결과가 바뀐 것 |
| `test/clone_and_speed.js` | clone 결정성, 속도 측정 |
| `test/live_snapshot.json` | 실제 페이지에서 읽은 판 (재구성 정확도 검증용) |

### python/suphago/

| 파일 | 역할 |
|---|---|
| `bridge.py` | `Engine`(워커 하나), `Game`(게임 하나), `State`(판 상태) |
| `agents.py` | 랜덤, 타입매칭, 몬테카를로 에이전트, 채점 공식, 큰 과일 보너스 |
| `encode.py` | 판 → 신경망 입력 (13채널 89×68 격자 + 과일 정보) |
| `model.py` | 가치망 `ValueNet`, 정책망 `PolicyNet`, 저장·불러오기 |
| `collect.py` | 기보 수집, 불러오기 (중복 제거, 끊긴 파일 허용) |
| `collect_branch.py` | 분기 기보 (기존 판에서 무작위 한 수 + MC 40수) |
| `train_value.py` | 가치망 학습 |
| `train_policy.py` | 정책망 학습 |
| `value_agent.py` | 가치망 에이전트(`value`), 가치망 도우미(`mcv`) |
| `search_agent.py` | 정책망 탐색(`ps`) |
| `bench.py` | 병렬 벤치마크 (중앙값, 25/75%) |
| `sweep.py` | 여러 MC 설정을 같은 시드로 한 큐에서 벤치 |
| `analyze.py` | 수박 제거와 판 길이 분석 |
| `feature_study.py` | 판 특징과 결과의 관계 분석 |
| `replay.py` | 한 판을 리플레이 파일로 기록 |
| `live.py` | 실제 사이트에서 플레이 |

## 데이터 흐름

```
[엔진] ──수집(collect)──> data/*.jsonl.gz ──학습(train_value, train_policy)──> runs/*.pt
   ▲                                                              │
   └───────────── 에이전트가 매 수 후보를 시뮬레이션 ◄─────────────┘
                         │
          벤치마크(bench) → results/      리플레이(replay) → replays/ → viewer/
          실제 사이트(live) → results/live/
```

## 병렬 처리

- `bench`, `collect`는 Python 스레드 여러 개가 각자 `Engine`(Node 프로세스)을 하나씩 갖고 서로 다른 판을 둡니다. `--workers`는 CPU 코어 수에 맞춥니다.
- 신경망을 CPU로 돌릴 때는 스레드끼리 코어를 뺏지 않게 PyTorch 스레드를 1개로 고정합니다.
- 한 프레임 비용의 약 70%가 충돌 판정이고, 판정 호출의 약 90%가 실제 접촉이라 결과를 바꾸지 않는 최적화 여지는 거의 없습니다. 속도는 병렬로 확보합니다.

## 클라우드

`cloud/run.sh`가 Google Cloud에 서버를 만들고, 코드와 모델을 올리고, 설치 후 엔진 해시를 확인한 뒤 `SUPHAGO_JOBS`로 정한 작업 스크립트를 백그라운드로 실행합니다. 작업이 끝나면 서버가 스스로 꺼집니다. 실행 방법은 [running.md](running.md)에 있습니다.
