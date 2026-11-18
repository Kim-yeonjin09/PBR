"""고정 초기 사전 실험. 실행: python Code/mujin_improved.py

기본 데이터: data_meaning_261111.csv. --data로 다른 CSV 지정 가능.
--check-data: API 호출 없이 데이터만 확인. --turns 생략 시 정답 후보 소진까지.
--resume 결과폴더: 이 버전으로 만든 실험을 이어 실행.

설치: python -m pip install openai
환경 변수 OPENAI_API_KEY 필요. 모델명은 아래 설정에서 변경 가능.
API 문서: https://developers.openai.com/api/docs/guides/text
"""
import argparse
import csv
import hashlib
import json
import math
import os
import random
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

SENDER_MODEL = "gpt-6-sol"
RECEIVER_MODEL = "gpt-6-sol"
SOUNDS = ["더", "예", "렁", "샤", "루"]
TURNS = None
DEFAULT_DATA = Path(__file__).resolve().with_name('data_meaning_261111.csv')
HISTORY_FORMAT = 'word_meaning_pairs_v1'
N = 20
P = 70.0
CONSECUTIVE = 2
# 중복 키로 덮어쓰지 않도록 (단어, 의미) 목록으로 보존한다.
# 초기 의미 대응 없이 시작한다. 아래 항목은 재사용할 수 있도록 주석으로 보존한다.
INITIAL_DICTIONARY = []
# INITIAL_DICTIONARY = [
#     ("루", "비둘기목의 새를 통틀어 이르는 말. 멧비둘기, 염주비둘기, 홍비둘기, 흑비둘기 따위의 여러 종류가 있다. 야생종과 집비둘기로 크게 나누는데 야생종은 대부분 텃새이다. 부리가 짧고 다리도 가늘고 짧으며 날개가 큰 편이다. 식도의 큰 모이주머니에 먹이를 저장하고 그 벽에서 암죽을 분비하여 새끼에게 먹인다. 성질이 온순하여 길들이기 쉽고 귀소성을 이용하여 통신에 사용한다. 평화를 상징하는 새이다."),
# ("루", "파충강 거북목의 동물을 통틀어 이르는 말. 몸은 타원형으로 납작하며 입은 각질이고 이가 없다. 등과 배에 단단한 딱지가 있어 머리와 꼬리, 지느러미 모양의 네발을 그 안으로 움츠릴 수 있다. 물가의 모래땅에 구멍을 파고 알을 낳는데 전 세계에 300여 종이 분포한다."),
# ("루", "꿩과의 새. 머리에 붉은 볏이 있고 날개는 퇴화하여 잘 날지 못하며 다리는 튼튼하다. 육용과 난용으로 육종된 수많은 품종이 있으며, 가금으로 가장 많이 사육한다. 원종은 인도, 말레이시아 등지의 들꿩이다."),
# ("샤", "길이가 발목까지 오는 바지."),
# ("샤", "바닥에 네 개의 작은 바퀴가 달린 스케이트. 주로 아스팔트나 콘크리트 바닥에서 탄다."),
# ('렁','해가 뜸.'),
# ('렁','태양계의 중심이 되는 항성. 지구에서 가장 가까운 거리에 있으며, 자전 주기는 약 25일이며 막대한 에너지를 방출하는 중심핵, 그 바깥쪽에 있는 복사층과 대류층, 그리고 빛을 직접 바깥으로 방출하는 광구·채층·코로나를 포함하는 대기층으로 이루어져 있다.'),
# ('예샤렁','우비(雨備)의 하나. 펴고 접을 수 있어 비가 올 때에 펴서 손에 들고 머리 위를 가린다. 박쥐우산, 비닐우산, 지우산 따위가 있다.'),
# ("예", "신문 기사를 실은 종이."),
# ("예", "안료를 전색제(展色劑)와 섞어서 만든 도료를 통틀어 이르는 말. 물체에 바르면 굳어져서 고운 빛깔을 내고 물체를 보호해 준다. 유성 페인트, 수성 페인트, 에나멜페인트 따위가 있다."),
# ("예", "물건을 넣어 들거나 메고 다닐 수 있게 만든 용구. 가죽이나 천, 비닐 따위로 만든다."),
# ("더", "바람의 힘을 기계적인 힘으로 바꾸는 장치. 큰 바퀴 주위에 얇은 판으로 날개를 달고 이것을 바람으로 회전시켜 그 회전력을 기계에 전하게 하며, 이때 생기는 힘을 정미(精米)·제분(製粉)·제재(製材)·양수(揚水) 따위에 쓴다."),
# ("더", "스포츠나 놀이로서 물속을 헤엄치는 일.")
# ]

SENDER_INSTRUCTIONS = """너는 새로운 언어 체계를 만드는 sender다.
Dictionary와 History를 참고하여 Input의 A(정답 의미)를 오답 의미 5개와
구분할 수 있는 단어를 만들어라. Words에 있는 단어만 이어 붙여라.
반복 사용은 허용된다. 설명, 공백, 문장 부호 없이 단어 하나만 출력하라.
완벽히 표현하기 어렵더라도 반드시 허용된 단어들로 결과를 만들어라.
판단 과정과 추론 요약은 가능한 한 한국어로 작성하되, 최종 답변은 단어 하나만 출력하라."""
RECEIVER_INSTRUCTIONS = """너는 모르는 언어를 해석하는 receiver다.
Dictionary와 History를 참고하여 Input의 단어가 뜻하는 의미를 보기에서 골라라.
출력은 정답 번호 하나만 써라. 설명이나 문장 부호를 붙이지 마라.
판단 과정과 추론 요약은 가능한 한 한국어로 작성하되, 최종 답변은 번호 하나만 출력하라."""


def numbered(meanings):
    return "\n".join(f"{i}. {m}" for i, m in enumerate(meanings, 1))


def context(dictionary, history):
    entries = "\n".join(f"{w}: {m}" for w, m in dictionary)
    past = "\n".join(f"{h['word']}: {h['meaning']}" for h in history)
    return f"[Dictionary]\n{entries}\n\n[History]\n{past}"


def call_model(client, model, prompt):
    started = time.perf_counter()
    role = "Sender" if prompt["instructions"] == SENDER_INSTRUCTIONS else "Receiver"
    print(f"{role} 요청 중...", flush=True)

    response = client.responses.create(
        model=model,
        reasoning={"effort": "low", "summary": "auto"},
        **prompt,
    )

    print(f"{role} 응답 완료: {time.perf_counter() - started:.1f}초", flush=True)
    usage = response.usage
    return {
        "model": model, "response_id": response.id,
        "request": prompt, "raw_output": response.output_text,
        "response_status": response.status,
        "usage": usage.model_dump(mode="json") if usage else None,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "reasoning_summary": [
            part.text
            for item in response.output
            if item.type == "reasoning"
            for part in item.summary
        ],
    }

def save_results(report, directory, started):
    turns = report['turns']
    graded = [t for t in turns if t.get('status') == 'completed']
    correct = sum(t['correct'] for t in graded)
    calls = [t[role] for t in turns for role in ('sender', 'receiver') if role in t]
    tokens = {key: sum((c.get('usage') or {}).get(key, 0) for c in calls)
              for key in ('input_tokens', 'output_tokens', 'total_tokens')}
    report['summary'] = {
        'requested_turns': report['settings']['turns'], 'completed_turns': len(graded),
        'correct_count': correct, 'incorrect_count': len(graded) - correct,
        'accuracy_percent': round(100 * correct / len(graded), 2) if graded else None,
        'invalid_sender_count': sum(t.get('sender_valid') is False for t in graded),
        'invalid_receiver_count': sum(t.get('receiver_valid') is False for t in graded),
        'api_responses_recorded': len(calls), 'tokens': tokens,
        'usage_missing_count': sum(c.get('usage') is None for c in calls),
        'elapsed_seconds': round(time.perf_counter() - started, 3),
    }
    s = report['summary']
    accuracy = f"{s['accuracy_percent']}%" if graded else '채점된 턴 없음'
    lines = ["전체 결과", f"실행 상태: {report['status']}",
             f"완료 턴: {len(graded)} / {s['requested_turns']}",
             f"정답률: {accuracy} ({correct}/{len(graded)})",
             f"정답 / 오답: {correct} / {s['incorrect_count']}",
             f"토큰 수: {tokens['total_tokens']} (입력 {tokens['input_tokens']}, 출력 {tokens['output_tokens']})",
             f"토큰 사용량 미제공 응답: {s['usage_missing_count']}",
             f"Sender 형식 위반: {s['invalid_sender_count']}, Receiver 형식 위반: {s['invalid_receiver_count']}",
             f"기록된 API 응답 수: {len(calls)}", f"소요 시간: {s['elapsed_seconds']}초",
             f"모델: sender={SENDER_MODEL}, receiver={RECEIVER_MODEL}",
             f"랜덤 시드: {report['settings']['seed']}",
             f"초기 사전: {len(INITIAL_DICTIONARY)}개 대응 관계 / {len({meaning for _, meaning in INITIAL_DICTIONARY})}개 고유 의미. 이후 문제에서 초기 의미 제외.",
             "정답률은 완료 턴 기준이며, 출력 형식 위반은 오답으로 처리한다.",
             "초기 사전은 고정한다. 정답 턴의 표현: 뜻만 History에 추가한다."]
    if report.get('error'):
        lines.append(f"실행 오류: {report['error']}")
    lines += ["", "턴별 상세 요약"]
    for t in turns:
        lines += ["", f"--- {t['turn']}턴 ({t['status']}) ---", "문제 보기:", numbered(t['choices']),
                  f"Sender에게 주어진 정답: {t['answer_number']}번 — {t['answer_meaning']}"]
        if 'sender' in t:
            lines.append(f"Sender 출력: {t['sender']['raw_output']!r}")
        if 'receiver' in t:
            lines.append(f"Receiver 출력: {t['receiver']['raw_output']!r}")
        if t.get('status') == 'completed':
            lines += [f"Receiver가 고른 의미: {t['receiver_meaning'] or '유효한 번호 없음'}",
                      f"결과: {'정답' if t['correct'] else '오답'}",
                      f"사전 갱신: {t['dictionary_added']}",
                      f"History 추가: {t['history_added']}"]
        for role in ('sender', 'receiver'):
            if role in t:
                lines.append(f"{role} 토큰 사용량: {json.dumps(t[role]['usage'], ensure_ascii=False)}")
    directory.mkdir(parents=True, exist_ok=True)
    settings = report['settings']
    metrics = evaluate(turns, settings.get('accuracy_N', N),
                       settings.get('accuracy_P_percent', P),
                       settings.get('accuracy_consecutive_blocks', CONSECUTIVE))
    report['accuracy_evaluation'] = {key: value for key, value in metrics.items() if key != 'per_turn'}
    report['checkpoint_saved_at_ns'] = time.time_ns()
    temporary = directory / f'.results_{uuid.uuid4().hex}.json'
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(5):
        try:
            temporary.replace(directory / 'results.json')
            break
        except PermissionError:
            if attempt == 4:
                recovery = directory / f'results.recovery_{time.time_ns()}.json'
                temporary.replace(recovery)
                print(f'[저장 경고] 기본 파일이 잠겨 복구 파일에 저장: {recovery}', flush=True)
            else:
                time.sleep(0.1 * 2 ** attempt)
    try:
        (directory / 'summary.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    except OSError as exc:
        print(f'[요약 저장 경고] 결과 JSON은 저장되었습니다: {exc}', flush=True)
    if not turns or turns[-1].get('status') != 'in_progress':
        save_accuracy(metrics, directory)


# accuracy.py와 동일한 평가/그래프 구현. 실행 시 다른 실험 모듈을 import하지 않는다.
def evaluate(turns, n=N, p=P, consecutive=CONSECUTIVE):
    if n < 1 or consecutive < 1 or not math.isfinite(p) or not 0 <= p <= 100:
        raise ValueError('N과 consecutive는 1 이상, P는 0~100이어야 합니다.')
    # 실패/중단된 API 호출은 채점하지 않는다. 완료된 형식 위반은 오답으로 포함한다.
    completed = [t for t in turns if t.get('status') == 'completed']
    rows, blocks = [], []
    correct_total = streak = 0
    first = stable = None
    needed = math.ceil(n * p / 100)
    for i, turn in enumerate(completed, 1):
        correct_total += bool(turn['correct'])
        window = completed[max(0, i - n):i]
        rolling = 100 * sum(bool(t['correct']) for t in window) / n if i >= n else None
        rows.append({
            'turn': turn['turn'], 'correct': int(bool(turn['correct'])),
            'cumulative_accuracy_percent': 100 * correct_total / i,
            'rolling_accuracy_percent': rolling,
            'history_added': turn.get('history_added'),
        })
        if i % n == 0:
            segment = completed[i - n:i]
            count = sum(bool(t['correct']) for t in segment)
            passed = count >= needed
            block = {'block': i // n, 'start_turn': segment[0]['turn'],
                     'end_turn': turn['turn'], 'correct_count': count,
                     'accuracy_percent': 100 * count / n, 'passed': passed}
            blocks.append(block)
            streak = streak + 1 if passed else 0
            if passed and first is None:
                first = turn['turn']
            if streak >= consecutive and stable is None:
                stable = {'confirmed_at_turn': turn['turn'],
                          'start_turn': blocks[-consecutive]['start_turn'],
                          'end_turn': turn['turn']}
    return {'N': n, 'P_percent': p, 'consecutive_blocks': consecutive,
            'required_correct_per_block': needed,
            'rule': 'non_overlapping_complete_blocks',
            'completed_turns': len(completed),
            'pending_block_turns': len(completed) % n,
            'first_passing_block_end_turn': first, 'stable_target': stable,
            'blocks': blocks, 'per_turn': rows}


def export_file(path, write):
    """보조 파일은 임시 파일로 완성한 뒤 교체한다. 잠겨 있어도 실험은 계속한다."""
    temporary = path.with_name(f'.{path.stem}.{uuid.uuid4().hex}{path.suffix}')
    try:
        write(temporary)
        temporary.replace(path)
    except OSError as exc:
        print(f'[저장 경고] {path.name}: {exc}. 결과 JSON은 유지되며 다음 저장 때 재시도합니다.',
              flush=True)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def draw_graph(metrics, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    rows = metrics['per_turn']
    fig, (ax, outcomes) = plt.subplots(2, 1, figsize=(12, 7), sharex=True,
                                      gridspec_kw={'height_ratios': [4, 1]})
    x = [r['turn'] for r in rows]
    ax.plot(x, [r['cumulative_accuracy_percent'] for r in rows],
            label='Cumulative accuracy', color='#94a3b8')
    ax.plot(x, [r['rolling_accuracy_percent'] for r in rows],
            label=f"Last {metrics['N']} turns (full window)", color='#2563eb')
    blocks = metrics['blocks']
    ax.plot([b['end_turn'] for b in blocks], [b['accuracy_percent'] for b in blocks],
            'o--', color='#16a34a', label=f"Non-overlapping {metrics['N']}-turn blocks")
    ax.axhline(metrics['P_percent'], color='#dc2626', linestyle='--',
               label=f"Target {metrics['P_percent']:g}%")
    ax.axhline(100 / 6, color='#a16207', linestyle=':', label='Chance (1/6)')
    stable = metrics['stable_target']
    if stable:
        ax.axvspan(stable['start_turn'], stable['end_turn'], color='#16a34a', alpha=.08)
        ax.axvline(stable['confirmed_at_turn'], color='#15803d',
                   label=f"Target confirmed at turn {stable['confirmed_at_turn']}")
    ax.set(title=f"Accuracy by turn | N={metrics['N']}, P={metrics['P_percent']:g}%, "
                 f"consecutive blocks={metrics['consecutive_blocks']}",
           ylabel='Accuracy (%)', ylim=(-3, 103))
    ax.grid(alpha=.2)
    ax.legend(loc='upper left', fontsize=8)
    outcomes.scatter(x, [r['correct'] for r in rows], s=20,
                     c=['#16a34a' if r['correct'] else '#dc2626' for r in rows])
    outcomes.set(yticks=[0, 1], yticklabels=['Incorrect', 'Correct'],
                 ylim=(-.5, 1.5), xlabel='Turn')
    outcomes.grid(axis='x', alpha=.2)
    fig.tight_layout()
    try:
        export_file(directory / 'accuracy.png', lambda path: fig.savefig(path, dpi=160))
        export_file(directory / 'accuracy.svg', lambda path: fig.savefig(path))
    finally:
        plt.close(fig)


def save_accuracy(metrics, directory):
    directory.mkdir(parents=True, exist_ok=True)
    export_file(directory / 'accuracy.json', lambda path: path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8'))

    def write_csv(path):
        with path.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=[
                'turn', 'correct', 'cumulative_accuracy_percent',
                'rolling_accuracy_percent', 'history_added'])
            writer.writeheader()
            writer.writerows(metrics['per_turn'])
    export_file(directory / 'accuracy.csv', write_csv)
    stable = metrics['stable_target']
    lines = [f"판정: 겹치지 않는 {metrics['N']}턴 구간에서 {metrics['P_percent']:g}% 이상을 "
             f"{metrics['consecutive_blocks']}개 구간 연속 달성",
             f"각 구간에 필요한 정답: {metrics['required_correct_per_block']}/{metrics['N']}",
             f"완료 턴: {metrics['completed_turns']}",
             f"첫 목표 달성 구간의 종료 턴: {metrics['first_passing_block_end_turn']}",
             (f"안정 도달 확인: {stable['confirmed_at_turn']}턴 "
              f"(달성 구간 {stable['start_turn']}~{stable['end_turn']}턴)" if stable else
              '현재까지 안정 도달 조건 미충족'),
             f"미완성 구간: {metrics['pending_block_turns']}턴 (도달 판정에서 제외)",
             '최근 N턴 정확도는 시각화용이며, 도달 판정은 겹치지 않는 구간만 사용한다.',
             '목표 도달 후에도 계속하며, 기본 종료 조건은 정답 후보 소진이다.', '', '구간별 결과']
    lines += [f"{b['start_turn']}~{b['end_turn']}턴: {b['accuracy_percent']:.2f}% "
              f"({b['correct_count']}/{metrics['N']}) — {'달성' if b['passed'] else '미달'}"
              for b in metrics['blocks']]
    export_file(directory / 'accuracy_summary.txt', lambda path: path.write_text(
        '\n'.join(lines) + '\n', encoding='utf-8'))
    draw_graph(metrics, directory)


def load_data(data_path):
    """한글 원본 CSV와 기존 meaning CSV를 모두 읽는다. 뜻풀이는 고쳐 쓰지 않는다."""
    with Path(data_path).open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        columns = reader.fieldnames or []
        meaning_column = next((key for key in ('meaning', '정의', '뜻') if key in columns), None)
        if meaning_column is None:
            raise ValueError('CSV에 meaning, 정의, 뜻 중 하나의 열이 필요합니다.')
        meanings, labels = [], {}
        for row in reader:
            meaning = (row.get(meaning_column) or '').strip()
            if not meaning:
                continue
            if meaning not in labels:
                meanings.append(meaning)
                labels[meaning] = []
            label = (row.get('단어') or row.get('word') or '').strip()
            if label and label not in labels[meaning]:
                labels[meaning].append(label)
    return meanings, labels


def load_resume(path):
    path = Path(path)
    directory = path if path.is_dir() else path.parent
    candidates = ([directory / 'results.json', *directory.glob('results.recovery_*.json')]
                  if path.is_dir() or path.name == 'results.json' else [path])
    available, errors = [], []
    for candidate in candidates:
        try:
            report = json.loads(candidate.read_text(encoding='utf-8-sig'))
            if not isinstance(report, dict) or not isinstance(report.get('turns'), list):
                raise ValueError('turns 목록이 없습니다.')
            available.append((report.get('checkpoint_saved_at_ns', candidate.stat().st_mtime_ns),
                              candidate, report))
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f'{candidate}: {exc}')
    if not available:
        raise ValueError('읽을 수 있는 재개 기록이 없습니다.\n' + '\n'.join(errors))
    _, selected, report = max(available, key=lambda item: item[0])
    if report.get('settings', {}).get('history_format') != HISTORY_FORMAT or report['settings'].get('sampling_policy') != 'exclude_previous_targets_only':
        raise ValueError('이 버전에서 생성한 재개 기록이 아닙니다. 이전 실험은 해당 실행 코드에서 재개하세요.')
    print(f'재개 기록: {selected.resolve()}', flush=True)
    return selected, report


def sample_question(rng, remaining, pool):
    if len(remaining) >= 6:
        choices = rng.sample(remaining, 6)
        answer_number = rng.randint(1, 6)
    else:
        answer = rng.choice(remaining)
        previous = [meaning for meaning in pool if meaning not in remaining]
        choices = list(remaining) + rng.sample(previous, 6 - len(remaining))
        rng.shuffle(choices)
        answer_number = choices.index(answer) + 1
    return choices, answer_number


def run(client, data_path, output_dir, turns=TURNS, seed=42, resume_report=None,
        n=None, p=None, consecutive=None):
    saved = (resume_report or {}).get('settings', {})
    n = saved.get('accuracy_N', N) if n is None else n
    p = saved.get('accuracy_P_percent', P) if p is None else p
    consecutive = saved.get('accuracy_consecutive_blocks', CONSECUTIVE) if consecutive is None else consecutive
    evaluate([], n, p, consecutive)
    started = time.perf_counter() - (resume_report or {}).get('summary', {}).get('elapsed_seconds', 0)
    rng = random.Random(seed)
    dictionary = ([(e['word'], e['meaning']) for e in resume_report['initial_dictionary']]
                  if resume_report is not None else list(INITIAL_DICTIONARY))
    history = []
    initial_meanings = {m for _, m in dictionary}
    data, labels = load_data(data_path)
    pool = [m for m in data if m not in initial_meanings]
    signature = hashlib.sha256(json.dumps(pool, ensure_ascii=False).encode('utf-8')).hexdigest()
    if len(pool) < 6:
        raise ValueError('초기 사전 의미를 제외한 고유 정의가 최소 6개 필요합니다.')
    if resume_report is not None and resume_report['settings'].get('dataset_signature') != signature:
        raise ValueError('재개 기록과 CSV의 정의 목록이 다릅니다. 새 데이터로는 --resume 없이 시작하세요.')
    report = resume_report if resume_report is not None else {
        'started_at': datetime.now().astimezone().isoformat(), 'status': 'running',
        'settings': {'turns': turns, 'seed': seed, 'sounds': SOUNDS,
                     'sender_model': SENDER_MODEL, 'receiver_model': RECEIVER_MODEL,
                     'data_path': str(data_path.resolve()),
                     'memory_policy': 'correct_turns_only', 'history_format': HISTORY_FORMAT,
                     'dictionary_policy': 'fixed_initial_dictionary',
                     'sampling_policy': 'exclude_previous_targets_only',
                     'dataset_signature': signature,
                     'sender_instructions': SENDER_INSTRUCTIONS,
                     'receiver_instructions': RECEIVER_INSTRUCTIONS},
        'initial_dictionary': [{'word': w, 'meaning': m} for w, m in dictionary],
        'turns': [],
    }
    for index, record in enumerate(report['turns'], 1):
        if (record['turn'] != index or len(record['choices']) != 6
                or len(set(record['choices'])) != 6 or not 1 <= record['answer_number'] <= 6
                or record['answer_meaning'] != record['choices'][record['answer_number'] - 1]
                or (record['status'] != 'completed' and index != len(report['turns']))):
            raise ValueError('재개 기록의 턴 번호·보기·정답 또는 완료 순서가 올바르지 않습니다.')
        if record['status'] == 'completed' and record['correct']:
            history.append({'word': record['sender']['raw_output'].strip(), 'meaning': record['answer_meaning']})
    used = {t['answer_meaning'] for t in report['turns']}
    remaining = [m for m in pool if m not in used]
    maximum_turns = len(report['turns']) + len(remaining)
    turns = maximum_turns if turns is None else turns
    if not max(1, len(report['turns'])) <= turns <= maximum_turns:
        raise ValueError(f'총 턴 수는 {max(1, len(report["turns"]))}~{maximum_turns}이어야 합니다.')
    if resume_report is not None:
        def nested_tuple(value):
            return tuple(nested_tuple(item) for item in value) if isinstance(value, list) else value
        rng.setstate(nested_tuple(report['random_state']))
        output_dir.mkdir(parents=True, exist_ok=True)
        backup = output_dir / f'results_before_resume_{time.time_ns()}.json'
        backup.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    report['settings'].update(turns=turns, data_path=str(data_path.resolve()))
    report['settings'].update(accuracy_N=n, accuracy_P_percent=p,
                              accuracy_consecutive_blocks=consecutive)
    sounds = report['settings']['sounds']
    report.update(history=history, random_state=rng.getstate(), status='running')
    report.pop('error', None)
    completed = sum(t['status'] == 'completed' for t in report['turns'])
    try:
        for index in range(completed + 1, turns + 1):
            if index <= len(report['turns']):
                record = report['turns'][index - 1]
                record['status'] = 'in_progress'
                choices, answer_number = record['choices'], record['answer_number']
                answer = record['answer_meaning']
            else:
                choices, answer_number = sample_question(rng, remaining, pool)
                answer = choices[answer_number - 1]
                remaining.remove(answer)
                record = {'turn': index, 'status': 'in_progress', 'choices': choices,
                          'answer_number': answer_number, 'answer_meaning': answer,
                          'answer_words': labels[answer]}
                report['turns'].append(record)
            report['random_state'] = rng.getstate()
            print(f'[{index}/{turns}턴 시작] History {len(history)}개, 남은 정답 후보 {len(remaining)}개', flush=True)
            save_results(report, output_dir, started)
            shared = context(dictionary, history)
            sender_input = ('[Words]\n' + '\n'.join(sounds) + '\n\n' + shared
                            + '\n\n[Input]\nA: ' + answer + '\n'
                            + numbered([m for m in choices if m != answer]))
            sender_prompt = {'instructions': report['settings']['sender_instructions'], 'input': sender_input}
            if 'sender' not in record:
                record['sender'] = call_model(client, report['settings']['sender_model'], sender_prompt)
                save_results(report, output_dir, started)
            word = record['sender']['raw_output'].strip()
            sound_pattern = r'(?:' + '|'.join(re.escape(sound) for sound in sounds) + r')+'
            record['sender_valid'] = bool(re.fullmatch(sound_pattern, word)) and record['sender']['response_status'] == 'completed'
            # Receiver에게 현재 턴 정답/정답 번호는 전달하지 않는다.
            receiver_prompt = {
                'instructions': report['settings']['receiver_instructions'],
                'input': shared + '\n\n[Input]\n' + word + '\n\n' + numbered(choices),
            }
            if 'receiver' not in record:
                record['receiver'] = call_model(client, report['settings']['receiver_model'], receiver_prompt)
                save_results(report, output_dir, started)
            raw_number = record['receiver']['raw_output'].strip()
            valid = bool(re.fullmatch('[1-6]', raw_number)) and record['receiver']['response_status'] == 'completed'
            prediction = int(raw_number) if valid else None
            record.update(receiver_valid=valid, receiver_number=prediction,
                          receiver_meaning=choices[prediction - 1] if prediction else None,
                          correct=record['sender_valid'] and prediction == answer_number,
                          status='completed', dictionary_added=False, history_added=False)
            # 서로 같은 의미로 해석한 사례만 다음 턴의 공유 기록에 남긴다.
            if record['correct']:
                history.append({'word': word, 'meaning': answer})
                record['history_added'] = True
            report['final_dictionary'] = [{'word': w, 'meaning': m} for w, m in dictionary]
            save_results(report, output_dir, started)
            print(f"{index}/{turns}턴: sender={word!r}, receiver={raw_number!r}, {'정답' if record['correct'] else '오답'}\n"
                  f"  정답 단어: {', '.join(labels.get(answer, [])) or '(단어 열 없음)'}\n"
                  f"  정답 뜻: {answer}\n  Receiver가 고른 뜻: {record['receiver_meaning']}", flush=True)
        report['status'] = 'completed'
    except (Exception, KeyboardInterrupt) as exc:
        report['status'] = 'failed' if isinstance(exc, Exception) else 'interrupted'
        report['error'] = f'{type(exc).__name__}: {exc}'
        if report['turns'] and report['turns'][-1]['status'] == 'in_progress':
            report['turns'][-1]['status'] = 'failed'
        raise
    finally:
        report['final_dictionary'] = [{'word': w, 'meaning': m} for w, m in dictionary]
        try:
            save_results(report, output_dir, started)
        except OSError as save_error:
            if not report.get('error'):
                raise
            print(f'[최종 저장 실패] {save_error}', flush=True)
        print(f"저장 위치: {output_dir.resolve()}")
    return report


def main():
    parser = argparse.ArgumentParser(description='고정 사전으로 무진어 실험')
    parser.add_argument('--turns', type=int, default=TURNS, help='총 턴 수 제한. 생략하면 정답 후보 소진까지')
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--data', type=Path, default=None)
    parser.add_argument('--output', type=Path, default=None)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--resume', type=Path, help='이 버전에서 만든 결과 폴더 또는 results.json')
    mode.add_argument('--analyze', type=Path, help='기존 기록의 정확도 그래프만 생성 (API 호출 없음)')
    parser.add_argument('--N', '--n', type=int, default=None, help='평가 구간 길이 (기본 20턴)')
    parser.add_argument('--P', '--p', type=float, default=None, help='목표 정확도 (기본 70%%)')
    parser.add_argument('--consecutive', type=int, default=None, help='목표를 연속 달성할 구간 수 (기본 2)')
    parser.add_argument('--check-data', action='store_true', help='CSV만 확인하고 종료 (API 호출 없음)')
    args = parser.parse_args()
    if args.turns is not None and args.turns < 1:
        parser.error('--turns는 1 이상이어야 합니다.')
    if args.analyze:
        source, report = load_resume(args.analyze)
        saved = report['settings']
        n = args.N if args.N is not None else saved.get('accuracy_N', N)
        p = args.P if args.P is not None else saved.get('accuracy_P_percent', P)
        consecutive = args.consecutive if args.consecutive is not None else saved.get('accuracy_consecutive_blocks', CONSECUTIVE)
        metrics = evaluate(report['turns'], n, p, consecutive)
        output = args.output or source.parent
        save_accuracy(metrics, output)
        print(f"완료 {metrics['completed_turns']}턴: 정확도 분석 및 그래프 저장 {output.resolve()}")
        return
    resume_report = None
    if args.resume:
        resume_path, resume_report = load_resume(args.resume)
    saved = resume_report['settings'] if resume_report is not None else {}
    args.data = args.data or Path(saved.get('data_path', DEFAULT_DATA))
    args.seed = args.seed if args.seed is not None else saved.get('seed', 42)
    data, _ = load_data(args.data)
    initial = ({e['meaning'] for e in resume_report['initial_dictionary']} if resume_report is not None
               else {m for _, m in INITIAL_DICTIONARY})
    print(f'데이터: {args.data.resolve()}\n고유 정의 {len(data)}개 / 초기 사전 제외 {sum(m not in initial for m in data)}개', flush=True)
    if args.check_data:
        return
    evaluate([], args.N if args.N is not None else saved.get('accuracy_N', N),
             args.P if args.P is not None else saved.get('accuracy_P_percent', P),
             args.consecutive if args.consecutive is not None else saved.get('accuracy_consecutive_blocks', CONSECUTIVE))
    import matplotlib  # 의존성 오류는 API 호출 전에 확인한다.
    from openai import OpenAI
    output = args.output or (resume_path.parent if args.resume else
                            Path(__file__).resolve().parent / 'mujin_results_261111' /
                            datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
    run(OpenAI(), args.data, output, args.turns, args.seed, resume_report=resume_report,
        n=args.N, p=args.P, consecutive=args.consecutive)


if __name__ == '__main__':
    main()
