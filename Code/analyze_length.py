"""Plot Sender expression length by turn without making API calls.

Usage:
    python Code/analyze_length.py PATH_TO_RESULTS_OR_FOLDER --window 20
    python Code/analyze_length.py tmp/grammar_snapshot.json --output Code/analysis/length_1072

Only completed turns are used. Each precomposed Korean syllable counts as one.
Outputs containing anything outside the experiment's allowed syllables are
reported and excluded from the plot and averages. Source files are never edited.
"""
import argparse
from collections import deque
import json
from pathlib import Path
import re
import statistics


def measure(report, window):
    sounds = report.get('settings', {}).get('sounds', ['더', '예', '렁', '샤', '루'])
    pattern = re.compile('(?:' + '|'.join(re.escape(s) for s in sounds) + ')+')
    rows, recent = [], deque(maxlen=window)
    seen = set()
    completed = sorted((t for t in report['turns'] if t.get('status') == 'completed'),
                       key=lambda t: t['turn'])
    for turn in completed:
        number = turn['turn']
        if number in seen:
            raise ValueError(f'중복된 턴 번호: {number}')
        seen.add(number)
        word = turn.get('sender', {}).get('raw_output', '').strip()
        valid = bool(pattern.fullmatch(word)) and turn.get('sender_valid', True) is not False
        length = len(re.findall('[가-힣]', word)) if valid else None
        recent.append(length)
        values = [v for v in recent if v is not None]
        rolling = statistics.mean(values) if len(recent) == window and values else None
        rows.append({'turn': number, 'word': word, 'syllables': length,
                     'valid': valid, 'correct': turn.get('correct'),
                     'meaning': turn.get('answer_meaning'), 'rolling_mean': rolling})
    return rows


def plot(rows, window, directory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import MaxNLocator

    valid = [r for r in rows if r['valid']]
    if not valid:
        raise ValueError('그래프를 그릴 수 있는 유효한 완료 턴이 없습니다.')
    fig, ax = plt.subplots(figsize=(15, 5.5), constrained_layout=True)
    # None creates a gap rather than connecting across an invalid output.
    ax.plot([r['turn'] for r in rows], [r['syllables'] for r in rows],
            color='#cbd5e1', linewidth=0.7, zorder=1)
    for outcome, color, label in [(True, '#16a34a', 'Correct'),
                                   (False, '#dc2626', 'Incorrect'),
                                   (None, '#64748b', 'Ungraded')]:
        group = [r for r in valid if r['correct'] is outcome]
        if group:
            ax.scatter([r['turn'] for r in group], [r['syllables'] for r in group],
                       s=13, alpha=0.6, color=color, label=label, zorder=2)
    ax.plot([r['turn'] for r in rows], [r['rolling_mean'] for r in rows],
            color='#2563eb', linewidth=2,
            label=f'{window}-turn rolling mean (valid outputs)', zorder=3)
    ax.set(xlabel='Turn', ylabel='Length (Korean syllables)',
           title='Sender expression length by turn', ylim=(0, None))
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.grid(axis='y', alpha=0.2)
    ax.legend(loc='upper left', framealpha=0.9)
    directory.mkdir(parents=True, exist_ok=True)
    for extension in ('png', 'svg'):
        fig.savefig(directory / f'syllable_length.{extension}', dpi=200)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('results', type=Path, help='results.json, 분석 스냅샷 JSON 또는 결과 폴더')
    parser.add_argument('--window', type=int, default=20, help='이동평균 구간 길이 (기본 20턴)')
    parser.add_argument('--output', type=Path, help='저장 폴더 (기본: 입력 파일 옆 length_analysis)')
    args = parser.parse_args()
    if args.window < 1:
        parser.error('--window는 1 이상이어야 합니다.')
    source = args.results / 'results.json' if args.results.is_dir() else args.results
    try:
        report = json.loads(source.read_text(encoding='utf-8-sig'))
        if not isinstance(report, dict) or not isinstance(report.get('turns'), list):
            raise ValueError('turns 목록을 포함하는 결과 JSON이 필요합니다.')
        rows = measure(report, args.window)
        output = args.output or source.parent / 'length_analysis'
        plot(rows, args.window, output)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(f'분석 실패: {exc}')
    valid = [r for r in rows if r['valid']]
    lengths = [r['syllables'] for r in valid]
    longest = max(valid, key=lambda r: r['syllables'])
    summary = {
        'source': str(source.resolve()), 'completed_turns': len(rows),
        'valid_turns': len(valid), 'excluded_invalid_turns': [r['turn'] for r in rows if not r['valid']],
        'mean_syllables': statistics.mean(lengths),
        'median_syllables': statistics.median(lengths), 'longest': longest,
        'window': args.window,
        'rolling_mean_policy': 'Full window of completed turns; invalid outputs excluded from its mean.',
        'per_turn': rows,
    }
    (output / 'syllable_length.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"완료 {len(rows)}턴 / 유효 {len(valid)}턴 / 형식 오류 제외 {len(rows) - len(valid)}턴")
    print(f"평균 {statistics.mean(lengths):.2f}음절 / 중앙값 {statistics.median(lengths):g}음절")
    print(f"최장: {longest['turn']}턴, {longest['syllables']}음절 — {longest['word']}")
    print(f"PNG·SVG 그래프와 턴별 JSON: {output.resolve()}")


if __name__ == '__main__':
    main()
