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
│ encode.py → model.py → train_value.py → value_agent.py  (AI)   │
│ collect.py 기보 수집 │ bench.py 벤치마크 │ replay.py 리플레이   │
│ live.py    실제 사이트에서 플레이 (Playwright)                  │
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
| `src/server.js` | 워커. 명령: `info`, `new`, `state`, `turn`, `clone`, `free`, `evaluate`, `expand`, `turnRecorded`, `load`, `run` |
| `test/compare_ref.js` | 원본 페이지에서 녹화한 24수와 비교 |
| `test/golden.js` | 4판 전체 상태 해시. 엔진 수정 후 값이 바뀌면 결과가 바뀐 것 |
| `test/clone_and_speed.js` | clone 결정성, 속도 측정 |
| `test/live_snapshot.json` | 실제 페이지에서 읽은 판 (재구성 정확도 검증용) |

### python/suphago/

| 파일 | 역할 |
|---|---|
| `bridge.py` | `Engine`(워커 하나), `Game`(게임 하나), `State`(판 상태) |
| `agents.py` | 랜덤, 타입매칭, 몬테카를로 에이전트와 채점 공식 |
| `encode.py` | 판 → 신경망 입력 (13채널 89×68 격자 + 과일 정보) |
| `model.py` | 가치망 CNN |
| `collect.py` | 기보 수집, 불러오기 |
| `train_value.py` | 가치망 학습 |
| `value_agent.py` | 가치망으로 후보를 채점하는 에이전트 |
| `bench.py` | 병렬 벤치마크 (중앙값, 25/75%) |
| `replay.py` | 한 판을 리플레이 파일로 기록 |
| `live.py` | 실제 사이트에서 플레이 |

## 데이터 흐름

```
[엔진] ──수집(collect)──> data/*.jsonl.gz ──학습(train_value)──> runs/*.pt
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

`cloud/run.sh`가 Google Cloud에 서버를 만들고, 코드와 모델을 올리고, 설치 후 엔진 해시를 확인한 뒤 `cloud/jobs.sh`를 백그라운드로 실행합니다. 작업이 끝나면 서버가 스스로 꺼집니다. 실행 방법은 [running.md](running.md)에 있습니다.
