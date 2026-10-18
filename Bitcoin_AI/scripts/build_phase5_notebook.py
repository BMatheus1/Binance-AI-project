"""Gera o notebook Colab reproduzível da Fase 5."""
from pathlib import Path

import nbformat as nbf


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "notebooks/phase5_kronos_colab_v2.ipynb"
COMPAT_OUT = ROOT / "notebooks/phase5_kronos_colab.ipynb"


def code(source: str):
    return nbf.v4.new_code_cell(source.strip())


def markdown(source: str):
    return nbf.v4.new_markdown_cell(source.strip())


cells = [
    markdown("""
# Bitcoin AI Trader — Fase 5: Kronos

Este notebook avalia **Kronos-mini** como challenger. Ele não envia ordens, não altera os modelos das Fases 1–4 e não acessa julho–setembro/2026. A sequência obrigatória é: validar GPU e hashes → inferência pré-treinada → smoke de fine-tuning → experimento completo opcional.

**Build Colab: 2026-10-18.3.** Esta versão não instala o `requirements.txt` oficial e não depende do diretório corrente da sessão.

O pré-treinamento divulgado do Kronos inclui Binance até junho/2024. Por isso o fine-tuning local começa em julho/2024, a calibração usa janeiro–março/2026 e a comparação usa abril–junho/2026. A comparação continua exploratória porque esse último bloco já foi usado na Fase 4.
"""),
    code("""
#@title 1. Preparar o Kronos sem alterar as bibliotecas-base do Colab
from pathlib import Path
import os, shutil, subprocess, sys

NOTEBOOK_BUILD = '2026-10-18.3'
CONTENT = Path('/content')
REPOSITORY = CONTENT / 'Kronos'
ISOLATED_DEPS = CONTENT / 'phase5_deps'
os.chdir(CONTENT)

subprocess.run(['nvidia-smi'], check=True)
shutil.rmtree(REPOSITORY, ignore_errors=True)
subprocess.run(['git', 'clone', '-q', 'https://github.com/shiyu-coder/Kronos.git', str(REPOSITORY)], check=True)
subprocess.run(['git', '-C', str(REPOSITORY), 'checkout', '-q',
                '67b630e67f6a18c9e9be918d9b4337c960db1e9a'], check=True)

# Dependências do Kronos ficam isoladas. Nada é rebaixado ou atualizado no ambiente global.
shutil.rmtree(ISOLATED_DEPS, ignore_errors=True)
subprocess.run([
    sys.executable, '-m', 'pip', 'install', '-q', '--target', str(ISOLATED_DEPS),
    '--only-binary=:all:', '--no-deps',
    'einops==0.8.1', 'huggingface-hub==0.36.2', 'safetensors==0.7.0', 'tqdm==4.67.1'
], check=True)
sys.path.insert(0, str(ISOLATED_DEPS))

from huggingface_hub import PyTorchModelHubMixin
import einops, huggingface_hub, joblib, numpy, pandas, pyarrow, safetensors, sklearn, torch, tqdm
assert torch.cuda.is_available(), 'Selecione Runtime > Change runtime type > GPU'
for module in [einops, huggingface_hub, safetensors, tqdm]:
    assert Path(module.__file__).is_relative_to(ISOLATED_DEPS), f'Dependência fora do ambiente isolado: {module.__file__}'
print({
    'build': NOTEBOOK_BUILD,
    'python': sys.version.split()[0],
    'torch': torch.__version__,
    'cuda': torch.version.cuda,
    'gpu': torch.cuda.get_device_name(0),
    'einops': einops.__version__,
    'huggingface_hub': huggingface_hub.__version__,
    'safetensors': safetensors.__version__,
    'isolated_dependencies': str(ISOLATED_DEPS),
    'repository': subprocess.check_output(['git', '-C', str(REPOSITORY), 'rev-parse', 'HEAD'], text=True).strip(),
})
"""),
    code("""
#@title 2. Carregar o pacote exportado pelo Bitcoin AI Trader
from pathlib import Path
from google.colab import files
import zipfile, json, hashlib, shutil

archive = Path('/content/bitcoin_ai_phase5_colab.zip')
EXPECTED_ARCHIVE_SHA256 = '17b4793bf356ed77ce789f10467901fbbd07ba00f620f1337a4a188f3faf4632'
def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

if not archive.exists() or sha256(archive) != EXPECTED_ARCHIVE_SHA256:
    uploaded = files.upload()
    candidates = [(name, content) for name, content in uploaded.items()
                  if Path(name).name == 'bitcoin_ai_phase5_colab.zip']
    if len(candidates) != 1:
        raise ValueError('Selecione exatamente bitcoin_ai_phase5_colab.zip')
    archive.write_bytes(candidates[0][1])
assert archive.is_file(), archive
assert sha256(archive) == EXPECTED_ARCHIVE_SHA256, 'ZIP diferente do exportado pela Fase 5'
data_dir = Path('/content/phase5_data')
shutil.rmtree(data_dir, ignore_errors=True)
data_dir.mkdir()
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None, 'ZIP corrompido'
    assert all(not Path(name).is_absolute() and '..' not in Path(name).parts for name in z.namelist())
    z.extractall(data_dir)
manifest = json.loads((data_dir / 'manifest.json').read_text())

for artifact in manifest['artifacts']:
    assert sha256(data_dir / artifact['path']) == artifact['sha256'], artifact['path']
cfg = manifest['config']
assert cfg['forbidden_final_test_start'] == '2026-07-01'
assert manifest['forbidden_final_period_exported'] is False
print('Pacote íntegro:', len(manifest['artifacts']), 'artefatos', archive)
"""),
    code("""
#@title 3. Ambiente, sementes e pesos oficiais fixados
import sys, platform, random, time, shutil
sys.path.insert(0, '/content/Kronos')
import numpy as np
import pandas as pd
import torch
from model import Kronos, KronosTokenizer, KronosPredictor

assert torch.cuda.is_available(), 'Selecione Runtime > Change runtime type > GPU'
device = 'cuda:0'
random.seed(cfg['seed']); np.random.seed(cfg['seed']); torch.manual_seed(cfg['seed'])
torch.cuda.manual_seed_all(cfg['seed'])
tokenizer = KronosTokenizer.from_pretrained(cfg['tokenizer_id'], revision=cfg['tokenizer_revision']).to(device).eval()
model = Kronos.from_pretrained(cfg['model_id'], revision=cfg['model_revision']).to(device).eval()
predictor = KronosPredictor(model, tokenizer, device=device, max_context=cfg['lookback'])
print({'python': platform.python_version(), 'torch': torch.__version__,
       'gpu': torch.cuda.get_device_name(0), 'model_parameters': sum(p.numel() for p in model.parameters())})
"""),
    code("""
#@title 4. Ler os blocos e reafirmar as fronteiras temporais
train = pd.read_parquet(data_dir / 'candles_train.parquet')
cal_candles = pd.read_parquet(data_dir / 'candles_calibration.parquet')
val_candles = pd.read_parquet(data_dir / 'candles_validation.parquet')
cal_rows = pd.read_parquet(data_dir / 'comparison_calibration.parquet')
val_rows = pd.read_parquet(data_dir / 'comparison_validation.parquet')
for frame in [train, cal_candles, val_candles]:
    frame['timestamps'] = pd.to_datetime(frame['timestamps'], utc=True)
for frame in [cal_rows, val_rows]:
    frame['decision_time'] = pd.to_datetime(frame['decision_time'], utc=True)

all_candles = pd.concat([train, cal_candles, val_candles], ignore_index=True).drop_duplicates('timestamps')
all_candles = all_candles.sort_values('timestamps').reset_index(drop=True)
assert all_candles.timestamps.diff().dropna().eq(pd.Timedelta(minutes=1)).all()
assert train.timestamps.min() >= pd.Timestamp('2024-07-01', tz='UTC')
assert val_candles.timestamps.max() < pd.Timestamp('2026-07-01', tz='UTC')
position = pd.Series(np.arange(len(all_candles)), index=all_candles.timestamps)
print({'train': len(train), 'calibration': len(cal_candles), 'validation': len(val_candles),
       'calibration_comparison': len(cal_rows), 'validation_comparison': len(val_rows)})
"""),
    code("""
#@title 5. Adaptador de caminhos estocásticos para probabilidades comparáveis
FIELDS = ['open', 'high', 'low', 'close', 'volume', 'amount']
HORIZONS = cfg['horizons']

def paths_to_probabilities(paths, alpha):
    paths = np.asarray(paths, dtype=float)  # [paths, steps, 6]
    assert paths.ndim == 3 and paths.shape[2] == 6 and np.isfinite(paths).all()
    entry = paths[:, 0, 0]
    out = {}
    for h in HORIZONS:
        returns = paths[:, h - 1, 3] / entry - 1
        labels = np.where(returns < 0, 0, np.where(returns > 0, 2, 1))
        counts = np.bincount(labels, minlength=3).astype(float)
        probability = (counts + alpha) / (counts.sum() + 3 * alpha)
        out[h] = (probability, float(returns.mean()))
    return out

def context_for(decision_time):
    feature_time = pd.Timestamp(decision_time) - pd.Timedelta(minutes=1)
    i = int(position.loc[feature_time])
    start = i - cfg['lookback'] + 1
    stop = i + cfg['prediction_length'] + 1
    assert start >= 0 and stop <= len(all_candles)
    context = all_candles.iloc[start:i + 1]
    future_times = all_candles.timestamps.iloc[i + 1:stop]
    assert context.timestamps.max() < pd.Timestamp(decision_time)
    return context[FIELDS], context.timestamps, future_times

def infer_rows(rows, active_predictor, *, paths, variant, batch_size=8):
    records = []
    rows = rows.sort_values('decision_time').reset_index(drop=True)
    for left in range(0, len(rows), batch_size):
        batch = rows.iloc[left:left + batch_size]
        prepared = [context_for(t) for t in batch.decision_time]
        path_values = [[] for _ in range(len(batch))]
        for path_id in range(paths):
            torch.manual_seed(cfg['seed'] + left * 100 + path_id)
            generated = active_predictor.predict_batch(
                [x[0] for x in prepared], [x[1] for x in prepared], [x[2] for x in prepared],
                pred_len=cfg['prediction_length'], T=cfg['temperature'], top_p=cfg['top_p'],
                sample_count=1, verbose=False)
            for i, forecast in enumerate(generated):
                path_values[i].append(forecast[FIELDS].to_numpy(float))
        for (_, source), forecasts in zip(batch.iterrows(), path_values):
            converted = paths_to_probabilities(np.stack(forecasts), cfg['probability_smoothing_alpha'])
            for h, (probability, predicted_return) in converted.items():
                records.append({
                    'decision_time': source.decision_time, 'horizon': h, 'variant': variant,
                    'target': int(source[f'target_{h}m']), 'actual_return': float(source[f'return_{h}m']),
                    'entry_price': float(source.entry_price), 'exit_price': float(source[f'exit_price_{h}m']),
                    'event_end': source[f'event_end_{h}m'], 'p_down': probability[0],
                    'p_tie': probability[1], 'p_up': probability[2],
                    'predicted_return': predicted_return, 'path_count': paths})
        print(f'{variant}: {min(left + batch_size, len(rows))}/{len(rows)} decisões')
    return pd.DataFrame(records)
"""),
    code("""
#@title 6. Inferência pré-treinada obrigatória — smoke
smoke_pretrained = infer_rows(val_rows.iloc[:2], predictor, paths=4, variant='pretrained_raw_smoke', batch_size=2)
assert len(smoke_pretrained) == 2 * len(HORIZONS)
assert np.allclose(smoke_pretrained[['p_down','p_tie','p_up']].sum(axis=1), 1)
PRETRAIN_SMOKE_OK = True
display(smoke_pretrained)
"""),
    markdown("""
## Fine-tuning controlado

O smoke abaixo atualiza somente o predictor e mantém o tokenizer congelado. As janelas vêm exclusivamente de `candles_train.parquet` (julho/2024–dezembro/2025). A calibração posterior usa janeiro–março/2026. Nenhuma busca de hiperparâmetros é executada.
"""),
    code("""
#@title 7. Dataset causal e rotina de fine-tuning do predictor
from torch.utils.data import Dataset, DataLoader

class WindowDataset(Dataset):
    def __init__(self, frame, samples, seed):
        self.frame = frame.reset_index(drop=True)
        self.samples = samples
        self.window = cfg['lookback'] + cfg['prediction_length'] + 1
        rng = np.random.default_rng(seed)
        self.starts = rng.integers(0, len(frame) - self.window, size=samples)
    def __len__(self): return self.samples
    def __getitem__(self, item):
        window = self.frame.iloc[self.starts[item]:self.starts[item] + self.window]
        x = window[FIELDS].to_numpy(np.float32)
        x = np.clip((x - x.mean(0)) / (x.std(0) + 1e-5), -5, 5)
        ts = window.timestamps.dt
        stamp = np.stack([ts.minute, ts.hour, ts.weekday, ts.day, ts.month], axis=1).astype(np.float32)
        return torch.from_numpy(x), torch.from_numpy(stamp)

def token_loss(active_model, batch_x, batch_stamp):
    with torch.no_grad():
        token_0, token_1 = tokenizer.encode(batch_x, half=True)
    logits = active_model(token_0[:, :-1], token_1[:, :-1], batch_stamp[:, :-1])
    loss, _, _ = active_model.head.compute_loss(logits[0], logits[1], token_0[:, 1:], token_1[:, 1:])
    return loss

def fine_tune(active_model, steps, checkpoint_dir):
    assert PRETRAIN_SMOKE_OK
    active_model.train(); tokenizer.eval()
    for parameter in tokenizer.parameters(): parameter.requires_grad_(False)
    dataset = WindowDataset(train, samples=steps * cfg['fine_tune']['batch_size'], seed=cfg['seed'])
    loader = DataLoader(dataset, batch_size=cfg['fine_tune']['batch_size'], shuffle=False)
    optimizer = torch.optim.AdamW(active_model.parameters(), lr=cfg['fine_tune']['learning_rate'],
                                  weight_decay=cfg['fine_tune']['weight_decay'])
    losses = []
    for step, (batch_x, batch_stamp) in enumerate(loader, start=1):
        batch_x, batch_stamp = batch_x.to(device), batch_stamp.to(device)
        loss = token_loss(active_model, batch_x, batch_stamp)
        optimizer.zero_grad(); loss.backward()
        torch.nn.utils.clip_grad_norm_(active_model.parameters(), cfg['fine_tune']['gradient_clip'])
        optimizer.step(); losses.append(float(loss.detach()))
        if step == steps: break
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    active_model.save_pretrained(checkpoint_dir)
    active_model.eval()
    return losses
"""),
    code("""
#@title 8. Smoke de um passo de treinamento
checkpoint_root = Path('/content/phase5_output/checkpoints')
before = next(model.parameters()).detach().clone()
smoke_losses = fine_tune(model, cfg['fine_tune']['smoke_steps'], checkpoint_root / 'smoke_predictor')
assert np.isfinite(smoke_losses).all() and not torch.equal(before, next(model.parameters()).detach())
TRAIN_SMOKE_OK = True
print({'losses': smoke_losses, 'checkpoint': str(checkpoint_root / 'smoke_predictor')})
"""),
    markdown("""
## Experimento completo opcional

Execute a próxima célula somente depois dos dois smokes. `FULL_EXPERIMENT=False` produz um pacote técnico pequeno. Para a comparação congelada completa, altere para `True`; o processo fará inferência pré-treinada antes de carregar novamente os pesos para o fine-tuning.
"""),
    code("""
#@title 9. Inferência, calibração e fine-tuning completos
from sklearn.linear_model import LogisticRegression
import joblib

FULL_EXPERIMENT = False #@param {type:"boolean"}
output_dir = Path('/content/phase5_output'); output_dir.mkdir(exist_ok=True)

if FULL_EXPERIMENT:
    # Recarrega pesos originais: o smoke jamais contamina a inferência pré-treinada.
    model = Kronos.from_pretrained(cfg['model_id'], revision=cfg['model_revision']).to(device).eval()
    predictor = KronosPredictor(model, tokenizer, device=device, max_context=cfg['lookback'])
    pre_cal = infer_rows(cal_rows, predictor, paths=cfg['monte_carlo_paths'], variant='pretrained_raw')
    pre_val = infer_rows(val_rows, predictor, paths=cfg['monte_carlo_paths'], variant='pretrained_raw')

    def calibrated(cal_predictions, val_predictions, raw_name, calibrated_name):
        outputs, calibrators = [], {}
        for h in HORIZONS:
            c = cal_predictions[cal_predictions.horizon == h]
            v = val_predictions[val_predictions.horizon == h].copy()
            estimator = LogisticRegression(C=1.0, max_iter=1000, random_state=cfg['seed'])
            estimator.fit(np.log(np.clip(c[['p_down','p_tie','p_up']], 1e-9, 1)), c.target)
            raw = estimator.predict_proba(np.log(np.clip(v[['p_down','p_tie','p_up']], 1e-9, 1)))
            p = np.full((len(v), 3), 1e-9)
            p[:, estimator.classes_.astype(int)] = raw
            p /= p.sum(1, keepdims=True)
            v[['p_down','p_tie','p_up']] = p; v['variant'] = calibrated_name
            outputs.append(v); calibrators[h] = estimator
        joblib.dump(calibrators, output_dir / f'{calibrated_name}-calibrators.joblib')
        return pd.concat(outputs, ignore_index=True)

    pre_calibrated = calibrated(pre_cal, pre_val, 'pretrained_raw', 'pretrained_calibrated')
    # Nova cópia original para fine-tuning controlado.
    fine_model = Kronos.from_pretrained(cfg['model_id'], revision=cfg['model_revision']).to(device)
    train_losses = fine_tune(fine_model, cfg['fine_tune']['max_steps'], checkpoint_root / 'finetuned_predictor')
    fine_predictor = KronosPredictor(fine_model, tokenizer, device=device, max_context=cfg['lookback'])
    fine_cal = infer_rows(cal_rows, fine_predictor, paths=cfg['monte_carlo_paths'], variant='finetuned_raw')
    fine_val = infer_rows(val_rows, fine_predictor, paths=cfg['monte_carlo_paths'], variant='finetuned_raw')
    fine_calibrated = calibrated(fine_cal, fine_val, 'finetuned_raw', 'finetuned_calibrated')
    predictions = pd.concat([pre_val, pre_calibrated, fine_val, fine_calibrated], ignore_index=True)
    mode = 'full'; losses = train_losses
else:
    predictions = smoke_pretrained.copy()
    mode = 'smoke'; losses = smoke_losses

predictions.to_parquet(output_dir / 'kronos_predictions.parquet', compression='zstd', index=False)
print({'mode': mode, 'prediction_rows': len(predictions), 'training_steps': len(losses)})
"""),
    code("""
#@title 10. Manifesto, hashes e pacote de retorno
import subprocess
run_manifest = {
    'mode': mode, 'created_at': pd.Timestamp.now(tz='UTC').isoformat(),
    'official_repository_revision': cfg['official_repository_revision'],
    'model_id': cfg['model_id'], 'model_revision': cfg['model_revision'],
    'tokenizer_id': cfg['tokenizer_id'], 'tokenizer_revision': cfg['tokenizer_revision'],
    'lookback': cfg['lookback'], 'prediction_length': cfg['prediction_length'],
    'temperature': cfg['temperature'], 'top_p': cfg['top_p'],
    'monte_carlo_paths': cfg['monte_carlo_paths'] if mode == 'full' else 4,
    'fine_tune': cfg['fine_tune'], 'training_losses': losses,
    'environment': {'notebook_build': NOTEBOOK_BUILD, 'python': platform.python_version(),
                    'torch': torch.__version__, 'cuda': torch.version.cuda,
                    'gpu': torch.cuda.get_device_name(0), 'numpy': np.__version__,
                    'pandas': pd.__version__, 'einops': einops.__version__,
                    'huggingface_hub': huggingface_hub.__version__,
                    'safetensors': safetensors.__version__},
    'prediction_sha256': sha256(output_dir / 'kronos_predictions.parquet'),
    'forbidden_final_period_used': False, 'real_orders': False,
    'policy': cfg['policy'],
}
(output_dir / 'run_manifest.json').write_text(json.dumps(run_manifest, indent=2), encoding='utf-8')
return_zip = shutil.make_archive('/content/bitcoin_ai_phase5_results', 'zip', output_dir)
print(return_zip, sha256(return_zip))
files.download(return_zip)
"""),
    markdown("""
## Importação local

Extraia `bitcoin_ai_phase5_results.zip` para uma pasta e execute no projeto:

```powershell
$env:PYTHONPATH = 'src'
python scripts/import_phase5_results.py "C:\\caminho\\phase5_results"
```

O importador valida revisões, probabilidades, observações e fronteira temporal; calcula métricas e cenários econômicos nas mesmas linhas dos modelos congelados. Nenhum resultado promove o Kronos automaticamente.
"""),
]

notebook = nbf.v4.new_notebook(cells=cells, metadata={
    "accelerator": "GPU",
    "colab": {"name": "phase5_kronos_colab.ipynb", "provenance": []},
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python"},
})
OUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, OUT)
nbf.write(notebook, COMPAT_OUT)
print(OUT)
