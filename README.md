# SuphaGo

수박게임을 스스로 학습하는 AI 프로젝트입니다. playsuikagame.com과 같은 규칙·물리로 돌아가는 헤드리스 엔진 위에서 베이스라인 → 가치망 → MCTS + 자가학습 순서로 올라갑니다.

## 구조

```
engine/          Node + Matter.js 시뮬레이터
  src/suika.js   게임 엔진 (reset, turn, clone)
  src/server.js  JSON 줄 단위 워커 (Python이 서브프로세스로 실행)
  test/          원본 비교, clone 결정성, 상태 해시 테스트
python/suphago/
  bridge.py      Node 워커와 통신
  agents.py      랜덤, 타입매칭, 몬테카를로 베이스라인
  bench.py       병렬 벤치마크 (중앙값, 25/75%)
  encode.py      판 상태 → 신경망 입력 (13채널 89x68 격자 + 현재/다음 과일)
  collect.py     학습용 기보 수집 (게임별 상태, 행동, 점수)
  model.py       가치망 (CNN, 판 → 남은 점수 예측)
  train_value.py 가치망 학습
  value_agent.py 가치망으로 후보를 채점하는 탐색 에이전트
  replay.py      한 판을 리플레이 파일로 기록
  live.py        실제 playsuikagame.com에서 에이전트가 플레이
viewer/          리플레이 뷰어 (index.html)
replays/         샘플 리플레이
results/         벤치마크 결과
```

## 실행

```bash
cd engine && npm install && cd ..
cd python
python3 -m suphago.bench --agent random --games 30 --workers 8
python3 -m suphago.bench --agent typematch --games 30 --workers 8
python3 -m suphago.bench --agent mc --mode combined --plies 2 --games 30 --workers 10 --out mc.jsonl
```

기보 수집 (가치망 학습용):

```bash
python3 -m suphago.collect --agent mc --games 200 --workers 10 --out ../data/mc1
```

가치망 학습과 평가:

```bash
pip install -r requirements.txt
python3 -m suphago.train_value --data ../data/mc1 --epochs 15 --loader-workers 8 --out ../runs/value_mc1.pt
python3 -m suphago.bench --agent value --model ../runs/value_mc1.pt --games 30 --workers 10 --out value_mc1.jsonl
```

학습 옵션:
- `--horizon 30`: 정답을 "게임 끝까지 남은 점수" 대신 "앞으로 30수 동안 얻는 점수"로 바꿉니다. 먼 미래의 운에 덜 흔들려서 후보끼리의 차이를 배우기 쉽습니다.
- `--over-head`: "15수 안에 게임이 끝나는가"를 함께 예측합니다(`--over-within`으로 수 조정).

에이전트 옵션 (`bench`, `replay`, `live` 공통):
- `--risk 1`: 게임오버 확률 1당 1000점을 뺍니다(`--over-head`로 학습한 모델에서만 의미 있음).
- `--blend 10`: 몬테카를로 채점 공식 1점당 10점을 더합니다.

가치망 에이전트는 후보마다 다음 낙하 시점까지 시뮬레이션한 뒤 `얻은 점수 + 가치망 예측`으로 고릅니다. 시뮬레이션 복사본은 원래 볼 수 없는 다다음 과일까지 이미 뽑아둔 상태라, 그 과일은 5종 모두 넣어 평균을 냅니다.

리플레이 기록과 보기:

```bash
python3 -m suphago.replay --agent mc --plies 2 --seed 0 --out ../replays/mc2_seed0.json
cd .. && python3 -m http.server 8000   # 브라우저에서 http://localhost:8000/viewer/
```

뷰어는 `replays/index.json`에 있는 판을 목록으로 보여주고, 다른 리플레이 파일은 끌어다 놓거나 "파일 열기"로 열 수 있습니다. 판 아래 막대는 그 수에서 에이전트가 따져본 후보 위치별 점수이고, 빨간 선이 실제로 고른 위치입니다. 위치는 엔진이 기록한 값을 그대로 재생합니다(브라우저에서 다시 시뮬레이션하면 계산 오차로 다른 게임이 됩니다).

실제 사이트에서 플레이:

```bash
pip install playwright && python3 -m playwright install chromium
python3 -m suphago.live --agent mc --plies 2 --log live_mc2.json
python3 -m suphago.live --agent mc --seed 0      # 엔진 시드 0과 같은 과일 순서로
```

브라우저 창이 열리면 팝업을 직접 닫고 터미널에서 Enter를 누릅니다. 매 수마다 페이지가 다음 과일을 받을 수 있게 되면 물리를 잠깐 멈추고 모든 과일의 종류·위치·속도·회전을 읽어 엔진에 그대로 옮긴 뒤, 에이전트가 고른 x에 마우스를 클릭하고 물리를 다시 켭니다. `--no-pause`를 주면 멈추지 않고 실시간으로 둡니다. 게임이 끝나면 페이지가 점수를 공개 리더보드에 올립니다.

페이지에서 읽은 판을 엔진에 옮겨 4초 동안 같이 굴려보면 과일 위치 차이는 최대 0.1px입니다(`engine/test/live_snapshot.json`). 다만 같은 시드로 과일 순서를 맞춰도 한 판 전체 점수는 엔진과 같게 나오지 않습니다. 브라우저와 Node의 `Math.sin`/`Math.cos`가 마지막 자리에서 달라서, 수십 수가 지나면 두 판의 배치가 갈라지기 때문입니다.

클라우드에서 벤치마크·수집 (Google Cloud 스팟 VM):

```bash
bash cloud/run.sh start    # 서버 생성, 코드·모델 업로드, cloud/jobs.sh 실행 시작
bash cloud/run.sh status   # 진행 확인
bash cloud/run.sh fetch    # 결과 내려받기 (기보는 data/ 로 복사)
bash cloud/run.sh delete   # 서버 삭제
```

작업이 끝나면 서버가 스스로 꺼집니다. 꺼진 서버도 디스크 요금은 나오니 결과를 받은 뒤 꼭 삭제합니다. 돌릴 작업은 `cloud/jobs.sh`에서 고칩니다.

기보의 행동 x는 전체 정밀도로 저장해서, 시드와 함께 게임을 그대로 재현할 수 있습니다.

워커 하나가 Node 프로세스 하나라서 `--workers`는 CPU 코어 수에 맞추면 됩니다.

## 엔진

- 물리: Phaser 3.70.0에 들어 있는 Matter.js 0.19.0 소스를 그대로 사용
- 규칙: 원본 페이지에서 확인한 동작을 직접 구현 (원본 게임 코드는 포함하지 않음)

| 항목 | 값 |
|---|---|
| 중력 | y 1.5, scale 0.001 |
| 솔버 | position 6, velocity 4, restingThresh 4, restingThreshTangent 6 |
| 과일 | 원형(26각형), friction 1, frictionStatic 0.5, frictionAir 0.01, restitution 0, 0.75배 스케일 |
| 통 | 캔버스 654×724, 벽 x 55~599, 바닥 y 708 |
| 생성 | 첫 과일 체리 고정, 이후 작은 5종 균등 랜덤, 다음 과일 공개 |
| 낙하 | y 80, 다음 낙하까지 600ms (60Hz 36프레임, 120Hz 72프레임) |
| 점수 | 1, 3, 6, 10, 15, 21, 28, 36, 45, 55, 66 |
| 게임오버 | 다른 과일끼리 충돌할 때 한쪽의 (y - centerOffset.y/2) < 70 |

```js
const { SuikaGame } = require('./engine/src/suika');
const g = new SuikaGame({ seed: 1, displayHz: 60 });
g.turn(300);          // 현재 과일을 x=300에 떨어뜨리고 다음 낙하 가능 시점까지 진행
const b = g.clone();  // 탐색용 분기 (같은 수를 두면 같은 결과)
```

### 원본과의 일치 정도

- 원본 페이지에서 녹화한 24수 시나리오와 비교하면 점수·과일 구성은 끝까지 같고, 좌표는 약 9수까지 소수점 12자리까지 같습니다.
- 그 뒤 좌표가 벌어지는 건 브라우저와 Node의 `Math.sin`/`Math.cos` 결과가 마지막 자리에서 달라서입니다. 원본도 브라우저마다 같은 이유로 조금씩 다르게 돌아갑니다.

### 속도

한 프레임 비용의 약 70%가 충돌 판정(SAT)이고, 판정 호출의 약 90%가 실제 접촉이라 결과를 바꾸지 않는 최적화 여지는 거의 없습니다. 속도는 워커 병렬로 확보합니다.

## 검증

- `node engine/test/compare_ref.js`: 원본 녹화 시나리오(120Hz)와 비교
- `node engine/test/clone_and_speed.js`: clone 결정성, 속도
- `node engine/test/golden.js`: 상태 해시 (엔진 수정 후 값이 바뀌면 결과가 바뀐 것)
