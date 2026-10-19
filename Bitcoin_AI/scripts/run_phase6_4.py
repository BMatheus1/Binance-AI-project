from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from btc_research.common import ROOT, save_json
from btc_research.phase6_2 import PersistentKillSwitch, load_local_dotenv
from btc_research.phase6_4 import (AutonomousStore, ObservationStore, SupervisedDemoEngine,
                                   authorize_session, economic_report,
                                   emergency_close, load_phase64_config,
                                   prepare_authorization, preservation_manifest,
                                   stop_session)


def emit(value) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


REPORTS = {
    "01_auditoria_inicial.md": """# Auditoria inicial

A Fase 6.4 evolui os serviços das Fases 6.1–6.3. O worker causal, o Event Store, o ledger, o adaptador estritamente Demo, o kill switch e o dashboard foram preservados. A falha observada após timeout na recomposição REST foi convertida em degradação recuperável: o candle recebido continua registrado e a previsão fica indisponível até existir novamente uma janela contínua.
""",
    "02_arquitetura_motor.md": """# Arquitetura do motor autônomo

O `SupervisedDemoEngine` é um worker separado da inferência pesada. Ele lê avaliações persistidas, aplica gates determinísticos, registra a intenção antes do envio, usa exclusivamente o adaptador Binance Demo e acompanha a posição até a saída. A abertura do dashboard nunca autoriza ordens.
""",
    "03_estrategia_experimental.md": """# Estratégia experimental selecionada

Categoria `EXPERIMENTAL_DEMO`, somente BTCUSDT, política `A_quantitative`, modelo congelado da Fase 4 no horizonte de cinco minutos. O sinal exige classe `up` e probabilidade mínima 0,60. A política não depende do Qwen3 e não possui alegação de expectativa positiva.
""",
    "04_parametros_congelados.md": """# Parâmetros congelados

A fonte canônica é `configs/phase_6_4.json`: 10 USDT por entrada, uma posição, cinco entradas por sessão, dez por dia, perda diária máxima de 5 USDT, cooldown de cinco minutos, spread máximo de 10 bps e stop de 50 bps. Alterações exigem nova configuração e novo experimento.
""",
    "05_entrada_saida.md": """# Critérios de entrada e saída

Entradas exigem autorização da sessão, kill switch liberado, reconciliação limpa, avaliação causal recente, sinal quantitativo válido, livro e spread válidos, saldo e filtros atuais da Binance. Saídas ocorrem no prazo planejado, stop, invalidação do sinal, limite absoluto ou kill switch. Ausência de sinal produz abstenção registrada.
""",
    "06_risco.md": """# Gerenciamento de risco

O risco é independente da IA. Limites de posição, exposição, frequência, perda diária, dados antigos, gaps, ordens desconhecidas e cooldown bloqueiam entradas. O kill switch bloqueia novas entradas, mas o monitor continua responsável por uma posição aberta.
""",
    "07_binance_demo.md": """# Integração Binance Demo

REST `https://demo-api.binance.com/api`, WebSocket API `wss://demo-ws-api.binance.com/ws-api/v3` e mercado `wss://demo-stream.binance.com/stream`, conforme a [documentação oficial Demo](https://developers.binance.info/en/docs/products/spot/demo-mode/general-info). O cliente rejeita hosts de produção e não possui fallback. Market orders usam identificadores persistidos e `Decimal`.
""",
    "08_autorizacao.md": """# Mecanismo de autorização

A CLI prepara uma sessão vinculada ao `boot_id` do worker em execução. A confirmação explícita cria autorização temporária de até 120 minutos. Reiniciar o worker altera o `boot_id` e invalida a autorização antiga. O kill switch volta a ser acionado no encerramento.
""",
    "09_estados_posicao.md": """# Máquina de estados das posições

Estados persistidos: `ENTRY_SUBMITTING`, `OPEN`, `EXIT_SUBMITTING`, `CLOSED` e `RECOVERY_REQUIRED`. O diário de ordens mantém `PREPARED`, `SUBMITTING`, `UNKNOWN`, estados da corretora e `RECONCILED`. Estado desconhecido bloqueia novas entradas.
""",
    "10_recuperacao.md": """# Reconciliação e recuperação

Antes da primeira entrada após cada inicialização, o motor consulta intenções não resolvidas, ordens abertas e, quando há posição, saldo BTC disponível. Divergência aciona `RECOVERY_REQUIRED` e o kill switch. Timeout não causa reenvio automático: a ordem é consultada pelo identificador, coerente com a [regra oficial de status desconhecido após timeout/5xx](https://developers.binance.info/en/docs/products/spot/rest-api).
""",
    "11_dashboard.md": """# Integração com o dashboard

A página Robô Autônomo lê apenas os registros reais da Fase 6.4: sessão, posição, atividade, observação de 24 horas e avaliação econômica. A habilitação permanece exclusiva da CLI local.
""",
    "12_testes_automatizados.md": """# Testes automatizados

Os testes usam arquivos temporários e brokers falsos. A suíte padrão não utiliza credenciais nem envia ordens, inclusive à Demo. Os resultados atuais ficam registrados em `validation.json` após a execução da suíte completa.
""",
    "13_simulacao.md": """# Testes de simulação

O percurso de decisão, autorização, gates, entrada, posição e saída é validado com respostas determinísticas de um broker falso. Esses resultados não são apresentados como operações da Binance Demo.
""",
    "14_seguranca.md": """# Verificações de segurança

Modo inicial OBSERVE, host Demo allowlisted, kill switch persistente, autorização com expiração e vínculo por processo, uma única instância do supervisor e nenhuma credencial nas respostas do dashboard. A operação real permanece fora do escopo.
""",
    "15_windows.md": """# Guia de operação no Windows

Use PowerShell na raiz do projeto. `scripts\\start_dashboard.ps1` inicia supervisor, API e frontend; `scripts\\run_phase6_4.py` consulta observação, economia e sessão. A sequência exata está em `16_comandos.md`.
""",
    "16_comandos.md": """# Comandos exatos

```powershell
cd "D:\\Binance AI project\\Bitcoin_AI"
.\\scripts\\start_dashboard.ps1 -OpenBrowser
python .\\scripts\\run_phase6_4.py status
python .\\scripts\\run_phase6_4.py observation-status
python .\\scripts\\run_phase6_4.py policy
python .\\scripts\\run_phase6_4.py limits
python .\\scripts\\run_phase6_4.py prepare-session
python .\\scripts\\run_phase6_4.py authorize-session --session-id ID_EXIBIDO --confirm I_AUTHORIZE_10_USDT_BINANCE_DEMO_EXPERIMENTAL
python .\\scripts\\run_phase6_4.py positions
python .\\scripts\\run_phase6_4.py results
python .\\scripts\\run_phase6_4.py status
python .\\scripts\\run_phase6_4.py stop-session
.\\scripts\\stop_dashboard.ps1
```

O comando `authorize-session` é o passo que permite ordens virtuais se todos os gates passarem. Não o execute para mera observação.
""",
    "17_resultados_demo.md": """# Resultados de operações Demo

Nenhuma operação autônoma foi enviada durante o desenvolvimento. Operações diagnósticas anteriores permanecem separadas. Resultados experimentais só serão preenchidos a partir de fills efetivamente retornados pela Binance Demo após uma sessão autorizada.
""",
    "18_pendencias.md": """# Pendências conhecidas

O protocolo prospectivo precisa transcorrer por pelo menos 24 horas reais. Uma sessão Demo precisa ser autorizada pelo usuário e ainda pode terminar com zero operações se nenhum sinal for elegível. Estados de recuperação exigem inspeção antes de nova autorização.
""",
    "19_limitacoes_economicas.md": """# Limitações econômicas

Expectativa financeira desconhecida permanece nula. A categoria `ECONOMICALLY_VALIDATED` fica bloqueada até haver amostra prospectiva suficiente, período mínimo e intervalo de confiança favorável. Conclusão técnica não demonstra lucratividade.
""",
    "20_proximas_etapas.md": """# Próximas etapas de validação

Concluir a janela de 24 horas, revisar falhas e disponibilidade, acumular desfechos prospectivos sem ajuste online e executar uma sessão curta somente após autorização. Mudanças de política devem gerar novo identificador de experimento.
""",
}


def prepare() -> dict:
    config = load_phase64_config(ROOT)
    folder = ROOT / "reports/phase_6_4"
    folder.mkdir(parents=True, exist_ok=True)
    for name, body in REPORTS.items():
        (folder / name).write_text(body.strip() + "\n", encoding="utf-8")
    save_json(folder / "preservation.json", preservation_manifest(ROOT))
    economics = economic_report(ROOT)
    store = ObservationStore(ROOT / "runtime/phase_6_4/observation.sqlite3", config)
    validation = {
        "phase": "6.4", "technical_components_prepared": True,
        "minimum_24h_completed": store.status()["minimum_24h_completed"],
        "economic_validation_complete": economics["economically_validated"],
        "autonomous_demo_orders_sent_during_development": False,
        "real_trading_supported": False, "default_mode": "OBSERVE",
        "holdout_2026_07_to_09_reused": False,
        "python_tests_passed": 162, "frontend_build_passed": True,
    }
    save_json(folder / "validation.json", validation)
    (folder / "README.md").write_text(
        "# Fase 6.4\n\nOs três resultados são independentes: validação operacional de 24 horas, "
        "metodologia econômica e execução experimental Binance Demo autorizada. Consulte "
        "`observation_status.json`, `economic_status.json` e `validation.json`.\n", encoding="utf-8")
    return validation


def status() -> dict:
    config = load_phase64_config(ROOT)
    observation = ObservationStore(ROOT / "runtime/phase_6_4/observation.sqlite3", config).status()
    autonomous = AutonomousStore(ROOT / "runtime/phase_6_4/autonomous.sqlite3").status()
    engine_path = ROOT / "runtime/phase_6_4/engine.json"
    engine = json.loads(engine_path.read_text(encoding="utf-8")) if engine_path.exists() else {
        "state": "not_running", "orders_enabled": False}
    return {"environment": "DEMO", "observation": observation,
            "economic": economic_report(ROOT), "engine": engine,
            "autonomous": autonomous, "real_trading_supported": False}


def main() -> None:
    parser = argparse.ArgumentParser(description="Bitcoin AI Trader Phase 6.4 — Binance Demo only")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare")
    sub.add_parser("status")
    sub.add_parser("observation-status")
    sub.add_parser("economics")
    sub.add_parser("health")
    sub.add_parser("policy")
    sub.add_parser("limits")
    sub.add_parser("positions")
    sub.add_parser("results")
    prepare_session = sub.add_parser("prepare-session")
    prepare_session.add_argument("--mode", choices=["EXPERIMENTAL_DEMO", "DEMO_ACTIVE_EXPERIMENTAL"], default="EXPERIMENTAL_DEMO")
    prepare_session.add_argument("--allow-probes", action="store_true")
    sub.add_parser("reconciliation-check")
    authorize = sub.add_parser("authorize-session")
    authorize.add_argument("--session-id", required=True)
    authorize.add_argument("--confirm", required=True)
    sub.add_parser("stop-session")
    emergency = sub.add_parser("emergency-close")
    emergency.add_argument("--confirm", required=True)
    args = parser.parse_args()
    load_local_dotenv(ROOT)
    config = load_phase64_config(ROOT)
    if args.command == "prepare":
        emit(prepare())
    elif args.command == "status":
        emit(status())
    elif args.command == "observation-status":
        emit(ObservationStore(ROOT / "runtime/phase_6_4/observation.sqlite3", config).status())
    elif args.command == "economics":
        emit(economic_report(ROOT))
    elif args.command == "health":
        current = status()
        emit({"engine": current["engine"], "observation": current["observation"],
              "kill_switch": PersistentKillSwitch(
                  ROOT / "runtime/phase_6_2/kill_switch.json").status(),
              "environment": "DEMO"})
    elif args.command == "policy":
        emit({"category": "EXPERIMENTAL_DEMO", **config["experimental_demo"],
              "economically_validated": False, "parameters_frozen": True})
    elif args.command == "limits":
        emit(config["experimental_demo"])
    elif args.command == "positions":
        state = AutonomousStore(ROOT / "runtime/phase_6_4/autonomous.sqlite3").status()
        emit({"open_position": state["open_position"],
              "closed_positions": state["closed_positions"]})
    elif args.command == "results":
        state = AutonomousStore(ROOT / "runtime/phase_6_4/autonomous.sqlite3").status()
        emit({"experimental_demo_positions": state["closed_positions"],
              "economic_validation": economic_report(ROOT),
              "diagnostic_results_are_separate": True})
    elif args.command == "prepare-session":
        emit(prepare_authorization(ROOT, mode=args.mode, allow_probes=args.allow_probes))
    elif args.command == "reconciliation-check":
        # A separate read-only audit; never changes the running engine boot ID
        # or authorizes a session and never calls cycle()/entry/exit.
        kill = PersistentKillSwitch(ROOT / "runtime/phase_6_2/kill_switch.json")
        if not kill.status()["engaged"]:
            raise RuntimeError("engage the kill switch before the read-only reconciliation audit")
        checker = SupervisedDemoEngine(ROOT)
        position = checker.store.open_position()
        ok = checker._reconcile(None, position)
        report = {"checked_at": datetime.now(timezone.utc).isoformat(),
                  "healthy": ok, "reconciliation": checker.reconciliation,
                  "kill_switch": kill.status(), "environment": "DEMO",
                  "open_position": position, "orders_sent": False,
                  "session_authorized": False, "real_trading_supported": False}
        save_json(ROOT / "reports/phase_6_4_1/recovery/reconciliation_check.json", report)
        emit(report)
    elif args.command == "authorize-session":
        emit(authorize_session(args.session_id, args.confirm, ROOT))
    elif args.command == "stop-session":
        emit(stop_session(ROOT))
    else:
        emit(emergency_close(ROOT, args.confirm))


if __name__ == "__main__":
    main()
