"""Human-readable stock health report backed by the shared simulated reporting audit."""
from pathlib import Path
from performance_reports import build_account

REPORT_FILE = "paper/report.txt"


def build_report():
    report = build_account(Path('.'), 'stocks')
    lines = ["SIMULATED FORWARD PAPER PERFORMANCE REPORT", "Simulation only — no brokerage orders are sent.",
             "As of: " + report.get('as_of', 'unavailable')]
    for key, value in report['metrics'].items():
        lines.append(f"{key}: {'Unavailable' if value is None else value}")
    lines.extend(["Cash benchmark: zero interest; no external cash flows assumed.",
                  "Buy-and-hold: " + str(report['benchmark']['return_pct']), report['benchmark']['basis'],
                  "Source: " + report['benchmark']['source'], "DATA QUALITY"])
    lines.extend('- ' + warning for warning in report['warnings'])
    lines.append("Early simulated evidence is not proof of strategy profitability.")
    return '\n'.join(lines) + '\n'


def main():
    Path('paper').mkdir(exist_ok=True)
    report = build_report()
    Path(REPORT_FILE).write_text(report, encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()
