#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — Portail unifié Desjardins: Bermudan Swaption + CPG Portfolio Pricer.

Lancement:
    python app.py                → http://localhost:5000
    python app.py --port 8080    → http://localhost:8080
    PORT=8080 python app.py      → http://localhost:8080
"""
import os, sys, json, webbrowser, threading, tempfile, io, argparse, socket
from datetime import datetime
from contextlib import redirect_stdout
from sqlalchemy import create_engine, text

src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from flask import Flask, request, jsonify, send_file, send_from_directory
import yaml, numpy as np, openpyxl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

@app.route("/fonts/<path:filename>")
def serve_font(filename):
    return send_from_directory(os.path.join(BASE_DIR, "fonts"), filename)

@app.route("/d15-desjardins-logo-couleur.png")
def serve_logo():
    return send_from_directory(BASE_DIR, "d15-desjardins-logo-couleur.png")

# ═══════════════════════════════════════════════════════════════════════════
#  SHARED CSS + HEADER — used by both pages
# ═══════════════════════════════════════════════════════════════════════════

SHARED_HEAD = r"""<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
@font-face{font-family:'Desjardins Sans';src:url('/fonts/DesjardinsSans-Regular.woff2') format('woff2');font-weight:400;font-style:normal;font-display:swap}
@font-face{font-family:'Desjardins Sans';src:url('/fonts/DesjardinsSans-Bold.woff2') format('woff2');font-weight:700;font-style:normal;font-display:swap}
:root{--dj-green:#00874E;--dj-black:#383838;--dj-white:#FFFFFF;--dj-mint:#CCE7DC;--dj-grey:#E6E7E8;--bg:#f5f5f7;--bg2:#ffffff;--bg3:#fafafa;--card:#ffffff;--border:rgba(0,0,0,.06);--border-hi:var(--dj-green);--text:#1d1d1f;--text2:#6e6e73;--text3:#86868b;--accent:var(--dj-green);--accent2:#00a463;--green:var(--dj-green);--green-bg:rgba(0,135,78,0.06);--green-subtle:rgba(0,135,78,0.03);--red:#ff3b30;--red-bg:rgba(255,59,48,0.06);--amber:#ff9500;--amber-bg:rgba(255,149,0,0.06);--shadow-sm:0 1px 3px rgba(0,0,0,.04),0 1px 2px rgba(0,0,0,.06);--shadow:0 4px 16px rgba(0,0,0,.06),0 1px 3px rgba(0,0,0,.04);--radius:14px;--radius-sm:10px;--sans:'Desjardins Sans',-apple-system,BlinkMacSystemFont,'SF Pro Display',system-ui,sans-serif;--mono:'JetBrains Mono','SF Mono',ui-monospace,monospace}
*{margin:0;padding:0;box-sizing:border-box}
html{-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale;text-rendering:optimizeLegibility}
body{font-family:var(--sans);background:var(--bg);color:var(--text);min-height:100vh;line-height:1.5}
::selection{background:var(--dj-mint);color:var(--dj-black)}
.header{position:sticky;top:0;z-index:50;background:rgba(255,255,255,0.72);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);border-bottom:1px solid rgba(0,0,0,0.06);padding:0 32px;display:flex;align-items:center;justify-content:space-between;height:56px}
.header-left{display:flex;align-items:center;gap:14px}
.header-logo{height:32px}
.header h1{font-family:var(--sans);font-size:17px;font-weight:700;letter-spacing:-.3px;color:var(--text)}
.header h1 em{color:var(--accent);font-style:normal}
.header .subtitle{font-size:10px;color:var(--text3);font-family:var(--mono);letter-spacing:.2px}
.nav-tabs{display:flex;gap:2px;height:100%}
.nav-tab{display:flex;align-items:center;padding:0 18px;font-size:13px;font-weight:600;color:var(--text3);text-decoration:none;border-bottom:2px solid transparent;transition:all .2s}
.nav-tab:hover{color:var(--text)}.nav-tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.container{max-width:1480px;margin:0 auto;padding:28px 32px;display:grid;grid-template-columns:440px 1fr;gap:28px}
.container-single{max-width:960px;margin:0 auto;padding:32px}
.panel{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;box-shadow:var(--shadow-sm);transition:box-shadow .25s ease}
.panel:hover{box-shadow:var(--shadow)}
.panel-header{padding:16px 22px;border-bottom:1px solid var(--border);font-family:var(--sans);font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--text3);display:flex;align-items:center;gap:10px;background:var(--bg3)}
.panel-header .dot{width:7px;height:7px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 3px rgba(0,135,78,0.12)}
.panel-body{padding:20px 22px}
.section-label{font-family:var(--sans);font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.8px;color:var(--accent);margin:20px 0 10px;padding-bottom:6px;border-bottom:1px solid rgba(0,135,78,0.08)}.section-label:first-child{margin-top:0}
.field{margin-bottom:10px;display:grid;grid-template-columns:140px 1fr;align-items:center;gap:10px}
.field label{font-family:var(--sans);font-size:13px;color:var(--text2);font-weight:500}
.field input,.field select{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:9px 12px;color:var(--text);font-family:var(--mono);font-size:12px;outline:none;transition:border-color .2s,box-shadow .2s}
.field input:focus,.field select:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(0,135,78,0.1)}
.field select{cursor:pointer;-webkit-appearance:none;appearance:none;background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%2386868b' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");background-repeat:no-repeat;background-position:right 10px center;padding-right:28px}
.field-check{margin-bottom:10px;display:flex;align-items:center;gap:10px}
.field-check label{font-family:var(--sans);font-size:13px;color:var(--text2);font-weight:400;cursor:pointer}
.field-check input[type=checkbox]{width:18px;height:18px;cursor:pointer;accent-color:var(--accent);border-radius:4px}
.upload-zone{border:2px dashed rgba(0,135,78,0.2);border-radius:var(--radius);padding:24px;text-align:center;cursor:pointer;transition:all 0.3s;margin:12px 0;background:var(--green-subtle)}
.upload-zone:hover{border-color:var(--accent);background:rgba(0,135,78,0.05);transform:translateY(-1px);box-shadow:var(--shadow)}
.upload-zone.loaded,.upload-zone.ok{border-color:var(--green);border-style:solid;background:var(--green-bg)}
.upload-zone .icon{font-size:28px;margin-bottom:6px}.upload-zone .label{font-family:var(--sans);font-size:14px;color:var(--text2);font-weight:500}
.upload-zone .sublabel{font-size:12px;color:var(--text3);margin-top:4px}
.upload-zone.loaded .label,.upload-zone.ok .label{color:var(--green);font-weight:600}.upload-zone input[type=file]{display:none}
.file-info{font-family:var(--mono);font-size:11px;color:var(--green);padding:10px 14px;background:var(--green-bg);border-radius:var(--radius-sm);margin-top:8px;display:none;border:1px solid rgba(0,135,78,0.1)}
.file-info.show{display:block}
.btn-price,.btn{display:inline-block;padding:14px 28px;background:var(--dj-green);color:var(--dj-white);border:none;border-radius:var(--radius-sm);font-size:15px;font-weight:700;cursor:pointer;transition:all 0.25s;font-family:var(--sans);letter-spacing:.3px}
.btn-price{width:100%;margin-top:16px}
.btn-price:hover,.btn:hover{transform:translateY(-2px);box-shadow:0 8px 28px rgba(0,135,78,0.35);background:#007a46}
.btn-price:active,.btn:active{transform:translateY(0);box-shadow:var(--shadow)}
.btn-price:disabled,.btn:disabled{opacity:.4;cursor:not-allowed;transform:none;box-shadow:none}
.btn-price.running{background:var(--text3);animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}
.btn-export,.btn-sec{padding:12px 24px;background:var(--card);border:1px solid var(--border);color:var(--text2);border-radius:var(--radius-sm);font-size:13px;cursor:pointer;font-family:var(--sans);font-weight:600;transition:all .2s;box-shadow:var(--shadow-sm);display:inline-block}
.btn-export:hover,.btn-sec:hover{border-color:var(--accent);color:var(--accent);box-shadow:var(--shadow);transform:translateY(-1px)}
.data-section{margin-top:12px}.data-toggle{font-family:var(--sans);font-size:12px;color:var(--accent);cursor:pointer;padding:6px 0;font-weight:500;transition:color .2s}
.data-toggle:hover{color:#006f40}.data-area{display:none;margin-top:6px}.data-area.open{display:block}
.data-area textarea{width:100%;height:160px;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;color:var(--text);font-family:var(--mono);font-size:11px;line-height:1.6;resize:vertical;outline:none;transition:border-color .2s}
.data-area textarea:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(0,135,78,0.08)}.data-area label{display:block;font-family:var(--sans);font-size:11px;color:var(--text3);margin-bottom:4px}
.results-area{display:flex;flex-direction:column;gap:16px}
.result-cards{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
.rcard{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:18px;text-align:center;transition:all .25s;box-shadow:var(--shadow-sm)}
.rcard:hover{border-color:rgba(0,135,78,0.2);box-shadow:var(--shadow);transform:translateY(-1px)}
.rcard .label{font-family:var(--sans);font-size:10px;text-transform:uppercase;letter-spacing:1.8px;color:var(--text3);margin-bottom:6px;font-weight:600}
.rcard .value{font-family:var(--mono);font-size:22px;font-weight:600;color:var(--text)}
.rcard .value.match{color:var(--green)}.rcard .sub{font-size:11px;color:var(--text3);margin-top:4px;font-family:var(--mono)}
.cmp-table,.results-table{width:100%;border-collapse:collapse;font-size:13px}
.cmp-table th,.results-table th{text-align:left;padding:10px 16px;font-family:var(--sans);font-size:10px;text-transform:uppercase;letter-spacing:1.2px;color:var(--text3);border-bottom:2px solid var(--border);font-weight:700;background:var(--bg3)}
.cmp-table td,.results-table td{padding:11px 16px;border-bottom:1px solid var(--border);font-family:var(--mono);font-size:12px}
.cmp-table tr:hover,.results-table tr:hover{background:var(--green-subtle)}
.cmp-table .name,.results-table .name{color:var(--text);font-family:var(--sans);font-weight:500}
.cmp-table .val{color:var(--text);text-align:right;font-weight:600}.cmp-table .bbg{color:var(--text2);text-align:right}.cmp-table .diff{text-align:right}
.diff-good{color:var(--green);font-weight:600}.diff-ok{color:var(--amber);font-weight:600}.diff-bad{color:var(--red);font-weight:600}
.model-bar{display:flex;gap:20px;padding:14px 22px;font-family:var(--mono);font-size:12px;color:var(--text2);flex-wrap:wrap;background:var(--bg3);border-bottom:1px solid var(--border)}
.model-bar span{color:var(--accent);font-weight:600}
.log-area{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius-sm);padding:16px;font-family:var(--mono);font-size:11px;line-height:1.7;color:var(--text3);max-height:220px;overflow-y:auto;white-space:pre-wrap}
.placeholder{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:400px;color:var(--text3);gap:14px;background:var(--card);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow-sm)}
.placeholder svg{opacity:.2;stroke:var(--text3)}.placeholder p{font-size:14px;color:var(--text3)}
.summary{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:16px 0}
.scard{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:16px;text-align:center;box-shadow:var(--shadow-sm)}
.scard .lbl{font-size:10px;text-transform:uppercase;letter-spacing:1.5px;color:var(--text3);margin-bottom:4px}
.scard .val{font-family:var(--mono);font-size:20px;font-weight:700;color:var(--accent)}
.scard .sub{font-size:10px;color:var(--text3);margin-top:2px}
.status{font-family:var(--mono);font-size:12px;padding:8px 14px;border-radius:8px;margin-top:10px;display:none}
.status.show{display:block}.status.ok{background:var(--green-bg);color:var(--green)}.status.err{background:var(--red-bg);color:var(--red)}
.scroll-left{max-height:calc(100vh - 84px);overflow-y:auto;padding-right:4px}
.scroll-left::-webkit-scrollbar{width:6px}.scroll-left::-webkit-scrollbar-track{background:transparent}.scroll-left::-webkit-scrollbar-thumb{background:rgba(0,0,0,.1);border-radius:99px}
@media(max-width:900px){.container{grid-template-columns:1fr;padding:16px}.result-cards,.summary{grid-template-columns:1fr 1fr}}
</style>"""

def _header_html(active, extra_right=""):
    brm = ' class="nav-tab active"' if active == "bermudan" else ' class="nav-tab"'
    cpg = ' class="nav-tab active"' if active == "cpg" else ' class="nav-tab"'
    return f'''<div class="header">
<div class="header-left"><img src="/d15-desjardins-logo-couleur.png" alt="Desjardins" class="header-logo" onerror="this.style.display='none'">
<div><h1>Desjardins <em>Analytics</em></h1><div class="subtitle">Portail de pricing · Produits dérivés &amp; CPG</div></div></div>
<nav class="nav-tabs"><a href="/"{brm}>Bermudan Swaption</a><a href="/cpg"{cpg}>CPG Portfolio</a></nav>
<div>{extra_right}</div></div>'''


# ═══════════════════════════════════════════════════════════════════════════
#  PAGE BODIES (HTML+JS for each pricer)
# ═══════════════════════════════════════════════════════════════════════════

BERMUDAN_BODY = r"""
<div class="container">
<div class="scroll-left">
<div class="panel">
<div class="panel-header"><div class="dot"></div> Deal Parameters</div>
<div class="panel-body">
<div class="section-label">Deal</div>
<div class="field"><label>Valuation Date</label><input type="date" id="val_date" value="2026-02-11"></div>
<div class="field"><label>Notional</label><input type="number" id="notional" value="10000000" step="1000000"></div>
<div class="field"><label>Strike (%)</label><input type="number" id="strike" value="3.245112" step="0.000001"></div>
<div class="field"><label>Direction</label><select id="direction"><option value="Receiver">Receiver</option><option value="Payer">Payer</option></select></div>
<div class="field"><label>Swap Start</label><input type="date" id="swap_start" value="2027-02-12"></div>
<div class="field"><label>Swap End</label><input type="date" id="swap_end" value="2032-02-12"></div>
<div class="field"><label>Frequency</label><select id="frequency"><option value="SemiAnnual" selected>SemiAnnual</option><option value="Quarterly">Quarterly</option><option value="Annual">Annual</option></select></div>
<div class="field"><label>Day Count</label><select id="day_count"><option value="ACT/365" selected>ACT/365</option><option value="ACT/360">ACT/360</option><option value="30/360">30/360</option></select></div>
<div class="field"><label>Payment Lag</label><input type="number" id="payment_lag" value="2"></div>
<div class="field"><label>Currency</label><input type="text" id="currency" value="CAD"></div>
<div class="section-label">Model</div>
<div class="field"><label>Mean Reversion</label><input type="number" id="mean_rev" value="0.03" step="0.001"></div>
<div class="field-check"><input type="checkbox" id="calib_a"><label for="calib_a">Calibrate a (mean reversion)</label></div>
<div class="field"><label>FDM Grid</label><input type="number" id="fdm_grid" value="300"></div>
<div class="section-label">Calibration Mode</div>
<div class="field-check"><input type="checkbox" id="standalone_mode" onchange="toggleBBG()"><label for="standalone_mode">Standalone (no BBG)</label></div>
<div id="bbgSection">
<div class="section-label">BBG Valuation</div>
<div class="field"><label>NPV</label><input type="number" id="bbg_npv" value="255683.06" step="0.01"></div>
<div class="field"><label>ATM Strike (%)</label><input type="number" id="bbg_atm" value="2.922733" step="0.000001"></div>
<div class="field"><label>Yield Value (bp)</label><input type="number" id="bbg_yv" value="56.389" step="0.001"></div>
<div class="field"><label>Und. Premium (%)</label><input type="number" id="bbg_uprem" value="1.46175" step="0.00001"></div>
<div class="field"><label>Premium (%)</label><input type="number" id="bbg_prem" value="2.55683" step="0.00001"></div>
<div class="section-label">BBG Greeks</div>
<div class="field"><label>DV01</label><input type="number" id="bbg_dv01" value="2832.42" step="0.01"></div>
<div class="field"><label>Gamma (1bp)</label><input type="number" id="bbg_gamma" value="22.06" step="0.01"></div>
<div class="field"><label>Vega (1bp)</label><input type="number" id="bbg_vega" value="2542.10" step="0.01"></div>
<div class="field"><label>Theta (1 day)</label><input type="number" id="bbg_theta" value="-109.14" step="0.01"></div>
</div></div></div>
<div class="panel" style="margin-top:14px">
<div class="panel-header"><div class="dot" style="background:var(--amber)"></div> Market Data</div>
<div class="panel-body">
<div class="upload-zone" id="uploadZone" onclick="document.getElementById('fileInput').click()">
<div class="icon">📁</div><div class="label">Click to load market data (.xlsx)</div>
<div class="sublabel">Excel with sheets: Curve_CAD_OIS + BVOL_CAD_RFR_Normal</div>
<input type="file" id="fileInput" accept=".xlsx,.xls" onchange="uploadFile(this)">
</div>
<div class="file-info" id="fileInfo"></div>
<div class="data-section"><div class="data-toggle" onclick="toggleData('curve')">▸ Manual: Curve Data</div>
<div class="data-area" id="curveData"><label>date,discount_factor (one per line)</label><textarea id="curveText"></textarea></div></div>
<div class="data-section"><div class="data-toggle" onclick="toggleData('vol')">▸ Manual: Vol Surface</div>
<div class="data-area" id="volData"><label>BPx10 matrix</label><textarea id="volText"></textarea></div></div>
<button class="btn-price" id="btnPrice" onclick="runPricer()">▶ PRICE</button>
</div></div></div>
<div class="results-area" id="resultsArea">
<div class="placeholder"><svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 4-6"/></svg>
<p>Load market data, set deal parameters, click <strong>PRICE</strong></p></div>
</div></div>
<script>
const EXPIRY_LABELS=["1Mo","3Mo","6Mo","9Mo","1Yr","2Yr","3Yr","4Yr","5Yr","6Yr","7Yr","8Yr","9Yr","10Yr","12Yr","15Yr","20Yr","25Yr","30Yr"];
const TENOR_LABELS=["1Y","2Y","3Y","4Y","5Y","6Y","7Y","8Y","9Y","10Y","12Y","15Y","20Y","25Y","30Y"];
let loadedExpLabels=null;
function toggleBBG(){document.getElementById('bbgSection').style.display=document.getElementById('standalone_mode').checked?'none':'block'}
function toggleData(id){const el=document.getElementById(id+'Data');el.classList.toggle('open');const t=el.previousElementSibling;t.textContent=(el.classList.contains('open')?'▾':'▸')+t.textContent.slice(1)}
function fmt(n,dec=2){if(n===null||n===undefined)return'N/A';return parseFloat(n).toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec})}
function diffClass(pct){const a=Math.abs(pct);if(a<3)return'diff-good';if(a<10)return'diff-ok';return'diff-bad'}
function diffBpClass(d,r){const p=r?Math.abs(d/r*100):0;if(p<3)return'diff-good';if(p<10)return'diff-ok';return'diff-bad'}
function uploadFile(input){const file=input.files[0];if(!file)return;const fd=new FormData();fd.append('file',file);const info=document.getElementById('fileInfo'),zone=document.getElementById('uploadZone');info.className='file-info show';info.textContent='⟳ Reading '+file.name+'...';info.style.color='var(--amber)';info.style.background='var(--amber-bg)';fetch('/api/upload_excel',{method:'POST',body:fd}).then(r=>r.json()).then(data=>{if(data.error){info.textContent='✗ '+data.error;info.style.color='var(--red)';info.style.background='var(--red-bg)';return}loadedExpLabels=data.expiry_labels;document.getElementById('curveText').value=data.curve.map(r=>r[0]+','+r[1]).join('\n');document.getElementById('volText').value=data.vol_values.map(r=>r.join(',')).join('\n');zone.classList.add('loaded');zone.querySelector('.icon').textContent='✓';zone.querySelector('.label').textContent=file.name;zone.querySelector('.sublabel').textContent='Click to load a different file';info.textContent='✓ Loaded '+data.curve.length+' nodes + '+data.vol_values.length+'×'+data.vol_values[0].length+' vol';info.style.color='var(--green)';info.style.background='var(--green-bg)';}).catch(err=>{info.textContent='✗ '+err;info.style.color='var(--red)';info.style.background='var(--red-bg)'})}
function runPricer(){const btn=document.getElementById('btnPrice');btn.disabled=true;btn.classList.add('running');btn.textContent='⟳ PRICING...';const vL=document.getElementById('volText').value.trim().split('\n'),vV=vL.filter(l=>l.trim()).map(l=>l.split(/[,\t]+/).map(Number)),cL=document.getElementById('curveText').value.trim().split('\n'),cD=cL.filter(l=>l.trim()).map(l=>{const p=l.split(/[,\t]+/);return[p[0].trim(),parseFloat(p[1])]}),eL=loadedExpLabels||EXPIRY_LABELS.slice(0,vV.length),tL=TENOR_LABELS.slice(0,vV[0]?vV[0].length:15),sa=document.getElementById('standalone_mode').checked,bbg=sa?{npv:0,atm_strike:0,yield_value_bp:0,underlying_premium:0,premium:0,dv01:0,gamma_1bp:0,vega_1bp:0,theta_1d:0}:{npv:+document.getElementById('bbg_npv').value||0,atm_strike:+document.getElementById('bbg_atm').value||0,yield_value_bp:+document.getElementById('bbg_yv').value||0,underlying_premium:+document.getElementById('bbg_uprem').value||0,premium:+document.getElementById('bbg_prem').value||0,dv01:+document.getElementById('bbg_dv01').value||0,gamma_1bp:+document.getElementById('bbg_gamma').value||0,vega_1bp:+document.getElementById('bbg_vega').value||0,theta_1d:+document.getElementById('bbg_theta').value||0};fetch('/api/price',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({deal:{valuation_date:document.getElementById('val_date').value,notional:+document.getElementById('notional').value,strike:+document.getElementById('strike').value,direction:document.getElementById('direction').value,swap_start:document.getElementById('swap_start').value,swap_end:document.getElementById('swap_end').value,fixed_frequency:document.getElementById('frequency').value,day_count:document.getElementById('day_count').value,payment_lag:parseInt(document.getElementById('payment_lag').value),currency:document.getElementById('currency').value},model:{mean_reversion:+document.getElementById('mean_rev').value,calibrate_a:document.getElementById('calib_a').checked,fdm_time_grid:parseInt(document.getElementById('fdm_grid').value),fdm_space_grid:parseInt(document.getElementById('fdm_grid').value)},benchmark:bbg,curve_data:cD,vol_surface_data:{expiry_labels:eL,tenor_labels:tL,values:vV},exercise:{mode:"auto"},data_source:{mode:"manual"},greeks:{dv01_bump_bp:1,gamma_bump_bp:1,vega_bump_bp:1,compute_theta:true,theta_annualization:"none"},output:{print_console:false,export_excel:false}})}).then(r=>r.json()).then(data=>{btn.disabled=false;btn.classList.remove('running');btn.textContent='▶ PRICE';if(data.error){document.getElementById('resultsArea').innerHTML='<div class="panel"><div class="panel-header"><div class="dot" style="background:var(--red)"></div> Error</div><div class="panel-body"><div class="log-area" style="color:var(--red)">'+data.error+'</div></div></div>';return}renderResults(data,bbg)}).catch(err=>{btn.disabled=false;btn.classList.remove('running');btn.textContent='▶ PRICE';document.getElementById('resultsArea').innerHTML='<div class="panel"><div class="panel-body"><div class="log-area" style="color:var(--red)">'+err+'</div></div></div>'})}
function renderResults(d,bbg){const g=d.greeks,mb=d.moneyness_bp,sa=document.getElementById('standalone_mode').checked,hB=bbg.npv>0;let ns=sa?'standalone':'';if(hB){const p=((d.npv-bbg.npv)/bbg.npv*100);ns=`${p>=0?'+':''}${fmt(p,4)}% vs BBG`}let h=`<div class="result-cards"><div class="rcard"><div class="label">NPV</div><div class="value match">${fmt(d.npv)}</div><div class="sub">${ns}</div></div><div class="rcard"><div class="label">σ total</div><div class="value">${fmt(d.sigma_total*10000,2)}</div><div class="sub">bp</div></div><div class="rcard"><div class="label">Yield Value</div><div class="value">${fmt(d.yield_value,3)}</div><div class="sub">bps</div></div><div class="rcard"><div class="label">ATM Rate</div><div class="value">${fmt(d.fair_rate*100,4)}%</div><div class="sub">Moneyness: ${mb>=0?'+':''}${fmt(mb,1)} bp</div></div><div class="rcard"><div class="label">Premium</div><div class="value">${fmt(d.premium_pct,4)}%</div><div class="sub">of notional</div></div><div class="rcard"><div class="label">Und. NPV</div><div class="value">${fmt(d.underlying_npv)}</div><div class="sub">${fmt(d.underlying_prem_pct,4)}%</div></div></div>`;let mi=`a = <span>${d.a_used}</span> ${d.a_calibrated?'(calibrated)':'(fixed)'} | σ_ATM = <span>${fmt(d.sigma_atm*10000,2)} bp</span>`;if(hB)mi+=` + Δσ = <span>${fmt(d.delta_spread*10000,2)} bp</span> → σ_total = <span>${fmt(d.sigma_total*10000,2)} bp</span>`;else mi+=` (standalone)`;h+=`<div class="panel"><div class="panel-header"><div class="dot"></div> Model</div><div class="model-bar">${mi}</div></div>`;if(hB){const np=((d.npv-bbg.npv)/bbg.npv*100),ab=(d.fair_rate-bbg.atm_strike/100)*10000,yD=d.yield_value-bbg.yield_value_bp,uD=d.underlying_prem_pct-bbg.underlying_premium,pD=d.premium_pct-bbg.premium;const vR=[['NPV (CAD)',fmt(bbg.npv),fmt(d.npv),fmt(np,4)+'%',diffClass(np)],['ATM Strike (%)',fmt(bbg.atm_strike,6),fmt(d.fair_rate*100,6),fmt(ab,2)+' bp',diffBpClass(ab,bbg.atm_strike*100)],['Yield Value (bp)',fmt(bbg.yield_value_bp,3),fmt(d.yield_value,3),fmt(yD,3)+' bp',diffBpClass(yD,bbg.yield_value_bp)],['Und. Premium (%)',fmt(bbg.underlying_premium,5),fmt(d.underlying_prem_pct,5),fmt(uD,5)+'%',diffBpClass(uD*100,bbg.underlying_premium)],['Premium (%)',fmt(bbg.premium,5),fmt(d.premium_pct,5),fmt(pD,5)+'%',diffClass(pD/bbg.premium*100)]].map(r=>`<tr><td class="name">${r[0]}</td><td class="bbg">${r[1]}</td><td class="val">${r[2]}</td><td class="diff ${r[4]}">${r[3]}</td></tr>`).join('');h+=`<div class="panel"><div class="panel-header"><div class="dot"></div> Valuation — BBG</div><div class="panel-body" style="padding:0"><table class="cmp-table"><thead><tr><th>Metric</th><th style="text-align:right">BBG</th><th style="text-align:right">QL</th><th style="text-align:right">Diff</th></tr></thead><tbody>${vR}</tbody></table></div></div>`}const gk=[{n:'DV01',q:g.dv01,b:hB?bbg.dv01:null},{n:'Gamma',q:g.gamma_1bp,b:hB?bbg.gamma_1bp:null},{n:'Vega',q:g.vega_1bp,b:hB?bbg.vega_1bp:null},{n:'Theta',q:g.theta_1d,b:hB?bbg.theta_1d:null},{n:'Delta',q:g.delta_hedge,b:null},{n:'Und. DV01',q:g.underlying_dv01,b:null}];if(hB){const gr=gk.map(x=>{const df=x.b!=null?x.q-x.b:null,pc=(x.b&&x.b!==0)?(df/Math.abs(x.b)*100):null,dc=pc!==null?diffClass(pc):'';return`<tr><td class="name">${x.n}</td><td class="bbg">${x.b!=null?fmt(x.b):'—'}</td><td class="val">${fmt(x.q)}</td><td class="diff ${dc}">${df!=null?(df>=0?'+':'')+fmt(df):'—'}</td><td class="diff ${dc}">${pc!=null?(pc>=0?'+':'')+fmt(pc,1)+'%':'—'}</td></tr>`}).join('');h+=`<div class="panel"><div class="panel-header"><div class="dot"></div> Greeks — BBG</div><div class="panel-body" style="padding:0"><table class="cmp-table"><thead><tr><th>Greek</th><th style="text-align:right">BBG</th><th style="text-align:right">QL</th><th style="text-align:right">Diff</th><th style="text-align:right">%</th></tr></thead><tbody>${gr}</tbody></table></div></div>`}else{const gr=gk.map(x=>`<tr><td class="name">${x.n}</td><td class="val" style="text-align:right">${fmt(x.q)}</td></tr>`).join('');h+=`<div class="panel"><div class="panel-header"><div class="dot"></div> Greeks</div><div class="panel-body" style="padding:0"><table class="cmp-table"><thead><tr><th>Greek</th><th style="text-align:right">Value</th></tr></thead><tbody>${gr}</tbody></table></div></div>`}h+=`<div class="panel"><div class="panel-header"><div class="dot"></div> Execution Log</div><div class="panel-body"><div class="log-area">${d.log||''}</div></div></div>`;h+=`<button class="btn-export" onclick="window.location.href='/api/export'">⬇ Export Excel</button> <button class="btn-export" style="margin-left:8px;border-color:var(--amber)" onclick="window.location.href='/api/export_pbi'">📊 Power BI</button>`;document.getElementById('resultsArea').innerHTML=h}
</script>
"""

CPG_BODY = r"""
<div style="display:flex;min-height:100vh;font-family:var(--sans);background:var(--bg)">
<!-- SIDEBAR -->
<aside style="width:230px;flex-shrink:0;background:#1A1D21;display:flex;flex-direction:column;position:fixed;top:0;left:0;height:100vh;z-index:100;border-right:1px solid rgba(255,255,255,.07)">
<div style="padding:22px 20px 18px;border-bottom:1px solid rgba(255,255,255,.07);display:flex;align-items:center;gap:10px">
<div style="width:32px;height:32px;border-radius:8px;background:var(--dj-green);display:flex;align-items:center;justify-content:center;flex-shrink:0"><svg width="18" height="18" viewBox="0 0 18 18" fill="none"><path d="M6 5h4.5a3 3 0 010 6H6V5z" fill="white"/></svg></div>
<div><div style="font-size:15px;font-weight:800;color:#fff;letter-spacing:-.3px;line-height:1.1">Desjardins</div><div style="font-size:10px;color:rgba(255,255,255,.4);letter-spacing:.5px;font-weight:600">TRÉSORERIE</div></div>
</div>
<nav style="padding:14px 0;flex:1;overflow-y:auto">
<div class="snav-sec">Workspace CPG</div>
<a class="snav active" onclick="showPage('snapshot')" id="nav-snapshot"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1h-5v-6h-6v6H4a1 1 0 01-1-1V9.5z"/></svg>Snapshot</a>
<a class="snav" onclick="showPage('curves')" id="nav-curves"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M2 12c2-4 4-4 6 0s4 4 6 0 4-4 6 0"/></svg>Courbes &amp; Inputs</a>
<a class="snav" onclick="showPage('vol')" id="nav-vol"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M13 2L3 14h8l-1 8 10-12h-8l1-8z"/></svg>Volatilité</a>
<a class="snav" onclick="showPage('instruments')" id="nav-instruments"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2l9 4.5v9L12 20l-9-4.5v-9L12 2z"/><path d="M12 2v18M3 6.5l9 4.5 9-4.5"/></svg>Instruments CPG</a>
<a class="snav" onclick="showPage('pricing')" id="nav-pricing"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2v20"/><path d="M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/></svg>Pricing</a>
<a class="snav" onclick="showPage('risk')" id="nav-risk"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 2l8 4v6c0 5.5-3.8 10.7-8 12-4.2-1.3-8-6.5-8-12V6l8-4z"/></svg>Risques</a>
<a class="snav" onclick="showPage('export')" id="nav-export"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M12 5v10M7 12l5 5 5-5"/><path d="M5 18h14"/></svg>Exports</a>
</nav>
<div style="padding:14px 18px;border-top:1px solid rgba(255,255,255,.07)"><a href="/" style="font-size:11px;color:rgba(255,255,255,.35);text-decoration:none;display:flex;align-items:center;gap:6px"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><path d="M9 6l6 6-6 6"/></svg>Bermudan Swaption</a><div style="font-size:10px;color:rgba(255,255,255,.15);margin-top:6px">v2.0</div></div>
</aside>
<!-- MAIN -->
<div style="margin-left:230px;flex:1;display:flex;flex-direction:column;min-height:100vh">
<!-- Topbar -->
<div style="height:54px;background:rgba(255,255,255,.85);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);border-bottom:1px solid rgba(0,0,0,.06);display:flex;align-items:center;justify-content:space-between;padding:0 28px;position:sticky;top:0;z-index:50">
<div style="display:flex;align-items:center;gap:8px">
<span style="font-size:17px;font-weight:800;color:#1D1D1F;letter-spacing:-.3px">Portail</span>
<span style="font-size:17px;font-weight:800;color:var(--dj-green);letter-spacing:-.3px">Données</span>
<span style="font-size:17px;font-weight:800;color:#1D1D1F;letter-spacing:-.3px">Trésorerie</span>
<span style="color:#AEAEB2;margin:0 6px;font-size:12px">›</span>
<span style="font-size:13px;font-weight:600;color:#636366" id="breadcrumb">Snapshot</span>
</div>
<div style="display:flex;align-items:center;gap:12px">
<input type="date" id="evalDate" value="2026-02-26" onchange="updateEvalDate()" style="font-family:var(--mono);font-size:11px;padding:6px 10px;border:1px solid rgba(0,0,0,.06);border-radius:8px;background:#fff;color:#1D1D1F;outline:none">
<button class="btn" id="btnRun" onclick="runPricing()" disabled style="padding:10px 20px;font-size:13px">▶ Pricer</button>
<span style="font-size:12px;color:#8E8E93;font-family:var(--mono)" id="clock"></span>
<div style="width:7px;height:7px;border-radius:50%;background:#00A463;box-shadow:0 0 0 2px #E9F5F0"></div>
</div>
</div>
<div style="flex:1;padding:28px;max-width:1360px;width:100%">

<!-- PAGE: SNAPSHOT -->
<div class="wsp" id="page-snapshot"><div id="snapshotContent"><div class="wempty"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><path d="M3 3v18h18"/><path d="M7 16l4-8 4 4 4-6"/></svg><p>Charger courbe + trades, puis lancer le pricing</p></div></div></div>

<!-- PAGE: CURVES -->
<div class="wsp" id="page-curves" style="display:none">
<div class="wtabs" id="ctabs"><button class="wtab active" onclick="setCtab('cdf',this)">Courbe CDF</button><button class="wtab" onclick="setCtab('qc',this)">Contrôle qualité</button></div>
<div id="ctab-cdf">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-bottom:18px">
<div class="panel"><div class="panel-header"><div class="dot" style="background:var(--amber)"></div>Courbe CDF — SQL Staging<span class="bdg bdg-d" style="margin-left:auto">QRM_STAGING</span></div><div class="panel-body">
<div style="font-size:12px;color:var(--text3);margin-bottom:4px">CDF = CAD CDF (spread) + CAD OIS CORRA (base)</div>
<div style="font-size:11px;color:var(--text3);margin-bottom:12px">Dernier EvaluationDate ≤ date d'évaluation</div>
<button class="btn-sec" style="width:100%" onclick="fetchCurveCDF()" id="btnFetch">⚡ Charger la courbe CDF</button>
<div class="status" id="curveStatus"></div>
</div></div>
<div class="panel"><div class="panel-header"><div class="dot"></div>Courbe — Fichier CSV</div><div class="panel-body">
<div class="upload-zone" onclick="document.getElementById('curveFile').click()" style="margin:0;min-height:80px"><div class="icon">📄</div><div class="label">Upload CSV</div><div class="sublabel">termPoint, termType, TauxCDF</div><input type="file" id="curveFile" accept=".csv" onchange="loadCurveFile(this)"></div>
<div class="status" id="curveFileStatus"></div>
</div></div>
</div>
<div class="panel" id="curveChartP" style="display:none"><div class="panel-header"><div class="dot"></div>Courbe CDF — Visualisation<span class="bdg bdg-g" id="curveBdg" style="margin-left:auto"></span></div><div class="panel-body" style="padding:8px"><canvas id="curveCanvas" height="200" style="width:100%"></canvas></div></div>
<div class="panel" id="curveTableP" style="margin-top:18px;display:none"><div class="panel-header"><div class="dot"></div>Détail des points</div><div class="panel-body" style="padding:0;overflow-x:auto" id="curvePreview"></div></div>
</div>
<div id="ctab-qc" style="display:none">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
<div class="panel"><div class="panel-header"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2"><path d="M5 12l5 5L20 7"/></svg>Contrôle qualité</div><div class="panel-body" id="qcBody"><span style="color:var(--text3);font-size:13px">Charger la courbe d'abord</span></div></div>
<div class="panel"><div class="panel-header"><div class="dot"></div>Métadonnées</div><div class="panel-body" id="qcMeta"><span style="color:var(--text3);font-size:13px">—</span></div></div>
</div>
</div>
</div>

<!-- PAGE: VOL -->
<div class="wsp" id="page-vol" style="display:none">
<div style="display:flex;gap:12px;padding:14px 18px;border-radius:12px;background:#FFFBF5;border:1px solid #FDE68A;margin-bottom:20px">
<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FF9500" stroke-width="1.8" style="flex-shrink:0;margin-top:2px"><path d="M12 2L2 20h20L12 2z"/><path d="M12 9v4M12 17h.01"/></svg>
<div style="flex:1"><div style="font-size:14px;font-weight:700;color:#92400E;margin-bottom:4px">Mode actuel : Proxy de volatilité</div><div style="font-size:12px;color:#78350F;line-height:1.6">Aucune surface explicite chargée. Proxy paramétrique transparent.</div></div>
</div>
<div class="wtabs" id="vtabs"><button class="wtab active" onclick="setVtab('proxy',this)">Proxy paramétrique</button><button class="wtab" onclick="setVtab('upload',this)">Charger vol explicite</button></div>
<div id="vtab-proxy">
<div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">
<div class="panel"><div class="panel-header"><div class="dot" style="background:var(--amber)"></div>Paramètres du proxy</div><div class="panel-body">
<div class="prow"><div><div class="plbl">Vol de base</div><div class="pdsc">Vol normale flat (bp)</div></div><input type="number" id="volBase" value="65" step="5" class="pinp"></div>
<div class="prow"><div><div class="plbl">Pente (bp/an)</div><div class="pdsc">Incrément par année</div></div><input type="number" id="volSlope" value="-2" step="0.5" class="pinp"></div>
<div class="prow"><div><div class="plbl">Floor (bp)</div><div class="pdsc">Plancher volatilité</div></div><input type="number" id="volFloor" value="30" step="5" class="pinp"></div>
<button class="btn-sec" style="width:100%;margin-top:12px" onclick="applyVolProxy()">Appliquer le proxy</button>
</div></div>
<div class="panel"><div class="panel-header"><div class="dot"></div>Surface générée</div><div class="panel-body" id="volHeatArea">
<div style="padding:12px 14px;border-radius:10px;background:#F5F9FF;border:1px solid #BFDBFE;font-size:12px;color:#007AFF;line-height:1.6"><strong>Note :</strong> Proxy uniquement. Charger une surface Bloomberg pour un pricing exact.</div>
</div></div>
</div>
</div>
<div id="vtab-upload" style="display:none">
<div class="panel"><div class="panel-header"><div class="dot"></div>Charger une surface de vol explicite</div><div class="panel-body">
<div class="upload-zone" onclick="document.getElementById('volFile').click()" style="margin:0;padding:40px">
<div style="font-size:32px;margin-bottom:12px">📊</div><div class="label">Déposez un fichier Excel/CSV avec la matrice de vol</div>
<div class="sublabel">Format: matrice expiry × tenor, valeurs en bp (normal vol)</div>
<input type="file" id="volFile" accept=".csv,.xlsx" onchange="loadVolFile(this)">
</div><div class="status" id="volStatus"></div>
<div style="margin-top:16px;padding:12px 14px;border-radius:10px;background:#E9F5F0;border:1px solid #CCE7DC;font-size:12px;color:#006F40;line-height:1.6">Surface explicite → bascule automatique en <strong>Mode Vol Réelle</strong> et confiance élevée.</div>
</div></div>
</div>
</div>

<!-- PAGE: INSTRUMENTS -->
<div class="wsp" id="page-instruments" style="display:none">
<div class="panel"><div class="panel-header"><div class="dot"></div>Chargement des transactions</div><div class="panel-body">
<div class="upload-zone" onclick="document.getElementById('tradesFile').click()" style="margin:0"><div class="icon">📄</div><div class="label">Charger les transactions (.xlsx / .xls / .csv)</div>
<div class="sublabel">CodeTransaction, Montant, Coupon, Marge, Frequence, etc.</div>
<input type="file" id="tradesFile" accept=".xlsx,.xls,.csv" onchange="loadTradesFile(this)"></div>
<div style="font-size:11px;color:var(--text3);margin-top:10px"><a href="/cpg/api/download_trades_template" style="color:var(--accent);text-decoration:none">⬇ Modèle Excel (template)</a></div>
<div class="status" id="tradesStatus"></div>
</div></div>
<div class="panel" style="margin-top:16px;display:none" id="tradesPrevP"><div class="panel-header"><div class="dot"></div>Portefeuille CPG<span class="bdg bdg-d" style="margin-left:auto" id="tradesBdg"></span></div><div class="panel-body" style="padding:0;overflow-x:auto" id="tradesPrevB"></div></div>
</div>

<!-- PAGE: PRICING -->
<div class="wsp" id="page-pricing" style="display:none"><div id="pricingContent"><div class="wempty"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg><p>Résultats du pricing disponibles après exécution</p></div></div></div>

<!-- PAGE: RISK -->
<div class="wsp" id="page-risk" style="display:none"><div id="riskContent"><div class="wempty"><svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2"><path d="M12 2l8 4v6c0 5.5-3.8 10.7-8 12-4.2-1.3-8-6.5-8-12V6l8-4z"/></svg><p>Analyse de risque disponible après pricing</p></div></div></div>

<!-- PAGE: EXPORT -->
<div class="wsp" id="page-export" style="display:none">
<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:22px">
<div class="xcard" onclick="if(pricingDone)window.location.href='/cpg/api/export'"><div class="xicon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="1.8"><path d="M12 5v10M7 12l5 5 5-5"/><path d="M5 18h14"/></svg></div><div style="font-size:14px;font-weight:700;color:#2C2C2E">Résultats complets</div><div style="font-size:12px;color:#8E8E93;margin-top:4px;line-height:1.5">Excel: sommaire, pricing, courbe, vol</div><span class="bdg bdg-d" style="margin-top:10px">XLSX</span></div>
<div class="xcard"><div class="xicon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="1.8"><path d="M12 2l8 4v6c0 5.5-3.8 10.7-8 12-4.2-1.3-8-6.5-8-12V6l8-4z"/></svg></div><div style="font-size:14px;font-weight:700;color:#2C2C2E">Rapport de risque</div><div style="font-size:12px;color:#8E8E93;margin-top:4px;line-height:1.5">DV01 buckets, stress tests, scénarios</div><span class="bdg bdg-d" style="margin-top:10px">XLSX</span></div>
<div class="xcard"><div class="xicon"><svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="1.8"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg></div><div style="font-size:14px;font-weight:700;color:#2C2C2E">Cashflows projetés</div><div style="font-size:12px;color:#8E8E93;margin-top:4px;line-height:1.5">Flux futurs par instrument, DFs</div><span class="bdg bdg-d" style="margin-top:10px">CSV</span></div>
</div>
<div class="panel"><div class="panel-header"><div class="dot"></div>Journal d'exécution</div><div class="panel-body"><div class="log-area" id="logArea">Aucun log. Lancer le pricing d'abord.</div></div></div>
</div>

</div><!-- /padding -->
<footer style="padding:14px 28px;border-top:1px solid rgba(0,0,0,.06);display:flex;align-items:center;justify-content:space-between;font-size:11px;color:#AEAEB2"><span>Portail Données Trésorerie — CPG Workspace</span><span style="font-family:var(--mono)" id="footEval">EvalDate: 2026-02-26</span></footer>
</div></div>

<style>
.snav-sec{padding:0 18px 8px;font-size:10px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:rgba(255,255,255,.2);margin-top:6px}
.snav{display:flex;align-items:center;gap:10px;padding:10px 18px;cursor:pointer;font-size:13px;font-weight:400;color:rgba(255,255,255,.55);background:transparent;position:relative;transition:all .15s;text-decoration:none}
.snav:hover{color:rgba(255,255,255,.9);background:rgba(255,255,255,.06)}
.snav.active{color:#33BC82;font-weight:700;background:rgba(0,164,99,.15)}
.snav.active::before{content:'';position:absolute;left:0;top:8px;bottom:8px;width:3px;border-radius:0 3px 3px 0;background:#33BC82}
.snav svg{flex-shrink:0;opacity:.7}.snav.active svg{opacity:1}
.wsp{animation:wfade .25s ease}
@keyframes wfade{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
.wempty{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:300px;color:var(--text3);gap:14px;background:#fff;border:1px solid rgba(0,0,0,.06);border-radius:16px;box-shadow:0 1px 3px rgba(0,0,0,.04)}
.wempty svg{opacity:.15}.wempty p{font-size:14px}
.wtabs{display:flex;gap:2px;border-bottom:2px solid #E5E5EA;margin-bottom:20px}
.wtab{padding:10px 18px;font-size:13px;font-weight:500;color:#8E8E93;border:none;background:transparent;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-2px;transition:all .15s;font-family:var(--sans)}
.wtab:hover{color:#1D1D1F}.wtab.active{color:var(--dj-green);font-weight:700;border-bottom-color:var(--dj-green)}
.bdg{display:inline-flex;align-items:center;gap:4px;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;line-height:1.4;white-space:nowrap}
.bdg-d{background:#E5E5EA;color:#48484A;border:1px solid #D1D1D6}
.bdg-g{background:#E9F5F0;color:#006F40;border:1px solid #CCE7DC}
.bdg-a{background:#FFFBF5;color:#92400E;border:1px solid #FDE68A}
.bdg-r{background:#FFF5F5;color:#FF3B30;border:1px solid #FECACA}
.bdg-b{background:#F5F9FF;color:#007AFF;border:1px solid #BFDBFE}
.kpi{background:#fff;border:1px solid #E5E5EA;border-radius:14px;padding:20px 22px;box-shadow:0 1px 3px rgba(0,0,0,.04);display:flex;flex-direction:column;gap:6px;transition:box-shadow .2s,transform .2s}
.kpi:hover{box-shadow:0 4px 16px rgba(0,0,0,.06);transform:translateY(-1px)}
.kpi .kl{font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#8E8E93}
.kpi .kv{font-size:28px;font-weight:700;line-height:1;font-family:var(--mono);letter-spacing:-1px}
.kpi .ku{font-size:13px;font-weight:600;color:#8E8E93}
.kpi .ks{font-size:12px;color:#8E8E93}
.prow{display:flex;align-items:center;justify-content:space-between;padding:12px 14px;border-radius:10px;background:var(--bg3);border:1px solid rgba(0,0,0,.06);margin-bottom:8px}
.plbl{font-size:13px;font-weight:600;color:#2C2C2E}.pdsc{font-size:11px;color:#8E8E93;margin-top:2px}
.pinp{width:80px;text-align:right;font-family:var(--mono);font-size:14px;font-weight:700;color:var(--amber);background:transparent;border:1px solid rgba(0,0,0,.06);border-radius:8px;padding:6px 10px;outline:none}
.pinp:focus{border-color:var(--accent);box-shadow:0 0 0 3px rgba(0,135,78,0.1)}
.xcard{background:#fff;border:1px solid #E5E5EA;border-radius:16px;padding:24px;display:flex;flex-direction:column;gap:6px;box-shadow:0 1px 3px rgba(0,0,0,.04);cursor:pointer;transition:all .2s}
.xcard:hover{box-shadow:0 4px 16px rgba(0,0,0,.06);transform:translateY(-2px);border-color:var(--accent)}
.xicon{width:44px;height:44px;border-radius:12px;display:flex;align-items:center;justify-content:center;background:#E9F5F0;margin-bottom:8px}
@keyframes spin{to{transform:rotate(360deg)}}
.krbar{background:var(--bg);border-radius:3px;height:14px;width:120px;overflow:hidden;display:inline-block;vertical-align:middle}
.krbar-f{height:100%;border-radius:3px;background:var(--accent);transition:width .4s}
/* Override shared styles that conflict with workspace layout */
.panel-header{gap:8px}
.panel-header .dot{margin-right:2px}
.results-table td,.results-table th{padding:10px 14px}
</style>

<script>
let curveOk=false,tradesOk=false,pricingDone=false,volMode=2;
let pricingData=null,curveData=null,execLog='';
const PL={snapshot:'Snapshot',curves:'Courbes & Inputs',vol:'Volatilité',instruments:'Instruments CPG',pricing:'Pricing',risk:'Risques',export:'Exports'};

function showPage(id){document.querySelectorAll('.wsp').forEach(p=>p.style.display='none');document.querySelectorAll('.snav').forEach(n=>n.classList.remove('active'));document.getElementById('page-'+id).style.display='block';document.getElementById('nav-'+id).classList.add('active');document.getElementById('breadcrumb').textContent=PL[id]||id}
function updateEvalDate(){document.getElementById('footEval').textContent='EvalDate: '+document.getElementById('evalDate').value}
function checkReady(){document.getElementById('btnRun').disabled=!(curveOk&&tradesOk)}
function showSt(id,msg,ok){const el=document.getElementById(id);el.textContent=msg;el.className='status show '+(ok?'ok':'err')}
function fmt(n,dec){if(n==null||isNaN(n))return'—';return parseFloat(n).toLocaleString('fr-CA',{minimumFractionDigits:dec==null?2:dec,maximumFractionDigits:dec==null?2:dec})}
function fmtM(n){if(Math.abs(n)>=1e9)return fmt(n/1e9,2)+' Md';if(Math.abs(n)>=1e6)return fmt(n/1e6,2)+' M';return fmt(n,0)}

/* Clock */
!function(){const el=document.getElementById('clock');if(!el)return;function t(){el.textContent=new Date().toLocaleTimeString('fr-CA',{hour:'2-digit',minute:'2-digit'})}t();setInterval(t,30000)}();

/* Tabs */
function setCtab(id,btn){document.querySelectorAll('#ctabs .wtab').forEach(t=>t.classList.remove('active'));btn.classList.add('active');document.getElementById('ctab-cdf').style.display=id==='cdf'?'block':'none';document.getElementById('ctab-qc').style.display=id==='qc'?'block':'none'}
function setVtab(id,btn){document.querySelectorAll('#vtabs .wtab').forEach(t=>t.classList.remove('active'));btn.classList.add('active');document.getElementById('vtab-proxy').style.display=id==='proxy'?'block':'none';document.getElementById('vtab-upload').style.display=id==='upload'?'block':'none'}

/* CURVE: SQL */
function fetchCurveCDF(){
  const btn=document.getElementById('btnFetch'),ev=document.getElementById('evalDate').value;
  if(!ev){showSt('curveStatus','⚠ Entrer une date.',false);return}
  btn.disabled=true;btn.textContent='⟳ Chargement...';
  fetch('/cpg/api/fetch_curve_cdf',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({eval_date:ev})}).then(r=>r.json()).then(d=>{
    btn.disabled=false;btn.textContent='⚡ Charger la courbe CDF';
    if(d.error){showSt('curveStatus','⚠ '+d.error,false);curveOk=false}else{
      showSt('curveStatus','✓ '+d.points+' pts ('+d.range+')'+(d.EvaluationDate?' · '+d.EvaluationDate:''),true);
      curveOk=true;curveData=d.preview;document.getElementById('curveBdg').textContent='EvalDate: '+(d.EvaluationDate||ev);
      if(d.preview){showCurveTable(d.preview);drawCurveChart(d.preview);buildQC(d.preview,d)}
    }checkReady()
  }).catch(e=>{btn.disabled=false;btn.textContent='⚡ Charger la courbe CDF';showSt('curveStatus','⚠ '+e,false)})
}

/* CURVE: CSV */
function loadCurveFile(i){
  const f=i.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);
  fetch('/cpg/api/upload_curve',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{
    if(d.error){showSt('curveFileStatus','⚠ '+d.error,false);curveOk=false}else{
      showSt('curveFileStatus','✓ '+d.points+' pts ('+d.range+')',true);curveOk=true;curveData=d.preview;
      if(d.preview){showCurveTable(d.preview);drawCurveChart(d.preview)}
    }checkReady()
  })
}

/* CURVE TABLE */
function showCurveTable(rows){
  document.getElementById('curveTableP').style.display='block';
  let h='<table class="results-table"><thead><tr>';
  ['Term','Type','Spread CDF','Base OIS','Taux CDF','≈ Jours','≈ Années'].forEach(c=>h+='<th style="text-align:'+(c==='Term'||c==='Type'?'left':'right')+'">'+c+'</th>');
  h+='</tr></thead><tbody>';
  rows.forEach(r=>{
    const d=r.ApproxDays||r.days||0;
    h+='<tr><td class="name">'+(r.termPoint||'')+'</td><td style="color:var(--text3)">'+(r.termType||'')+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono);font-weight:600">'+fmt(r.ZeroCouponSpreadCDF||r.spread,4)+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono);font-weight:600">'+fmt(r.ZeroCouponBase||r.base,4)+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono);font-weight:700;color:var(--green)">'+fmt(r.TauxCDF||r.tauxCDF,4)+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono);color:var(--text3)">'+d+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono);color:var(--text3)">'+(d/365).toFixed(2)+'</td></tr>';
  });
  h+='</tbody></table>';document.getElementById('curvePreview').innerHTML=h;
}

/* CURVE CHART */
function drawCurveChart(rows){
  document.getElementById('curveChartP').style.display='block';
  const c=document.getElementById('curveCanvas'),ctx=c.getContext('2d');
  const W=c.parentElement.offsetWidth-32,H=200;c.width=W*2;c.height=H*2;c.style.width=W+'px';c.style.height=H+'px';ctx.scale(2,2);
  const pts=rows.map(r=>({x:r.ApproxDays||r.days||0,y:parseFloat(r.TauxCDF||r.tauxCDF||0)})).filter(p=>!isNaN(p.y));
  if(!pts.length)return;
  const xMin=0,xMax=Math.max(...pts.map(p=>p.x))*1.05,yMin=Math.min(...pts.map(p=>p.y))*0.95,yMax=Math.max(...pts.map(p=>p.y))*1.05;
  const pad={t:20,r:20,b:30,l:55},pw=W-pad.l-pad.r,ph=H-pad.t-pad.b;
  function tx(v){return pad.l+(v-xMin)/(xMax-xMin)*pw}
  function ty(v){return pad.t+(1-(v-yMin)/(yMax-yMin))*ph}
  ctx.fillStyle='#fff';ctx.fillRect(0,0,W,H);
  ctx.strokeStyle='#E5E5EA';ctx.lineWidth=.5;
  for(let i=0;i<5;i++){const y=yMin+(yMax-yMin)*i/4;ctx.beginPath();ctx.moveTo(pad.l,ty(y));ctx.lineTo(W-pad.r,ty(y));ctx.stroke();ctx.fillStyle='#8E8E93';ctx.font='10px JetBrains Mono';ctx.textAlign='right';ctx.fillText(y.toFixed(2)+'%',pad.l-6,ty(y)+3)}
  const grad=ctx.createLinearGradient(0,pad.t,0,H-pad.b);grad.addColorStop(0,'rgba(0,135,78,.12)');grad.addColorStop(1,'rgba(0,135,78,.01)');
  ctx.beginPath();ctx.moveTo(tx(pts[0].x),ty(pts[0].y));pts.forEach(p=>ctx.lineTo(tx(p.x),ty(p.y)));ctx.lineTo(tx(pts[pts.length-1].x),H-pad.b);ctx.lineTo(tx(pts[0].x),H-pad.b);ctx.closePath();ctx.fillStyle=grad;ctx.fill();
  ctx.beginPath();ctx.moveTo(tx(pts[0].x),ty(pts[0].y));pts.forEach(p=>ctx.lineTo(tx(p.x),ty(p.y)));ctx.strokeStyle='#00874E';ctx.lineWidth=2.5;ctx.stroke();
  pts.forEach(p=>{ctx.beginPath();ctx.arc(tx(p.x),ty(p.y),3.5,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.strokeStyle='#00874E';ctx.lineWidth=2;ctx.stroke()});
}

/* QC */
function buildQC(rows,d){
  const checks=[{l:'Monotonie des taux',ok:true,d:'Taux CDF croissants ✓'},{l:'Couverture temporelle',ok:true,d:'Plage: '+d.range},{l:'Date d\'évaluation',ok:true,d:d.EvaluationDate||'—'},{l:'Points',ok:rows.length>=10,d:rows.length+' points'}];
  let s=rows.map(r=>parseFloat(r.TauxCDF||r.tauxCDF||0));for(let i=1;i<s.length;i++)if(s[i]<s[i-1]){checks[0].ok=false;checks[0].d='Non monotone à i='+i;break}
  let h='';checks.forEach(c=>{h+='<div style="display:flex;align-items:flex-start;gap:10px;padding:12px 0;border-bottom:1px solid #E5E5EA"><div style="width:22px;height:22px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;background:'+(c.ok?'#E9F5F0':'#FFFBF5')+'"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="'+(c.ok?'var(--green)':'var(--amber)')+'" stroke-width="2">'+(c.ok?'<path d="M5 12l5 5L20 7"/>':'<path d="M12 2L2 20h20L12 2z"/>')+'</svg></div><div><div style="font-size:13px;font-weight:600;color:#2C2C2E">'+c.l+'</div><div style="font-size:12px;color:#8E8E93;margin-top:2px">'+c.d+'</div></div></div>'});
  document.getElementById('qcBody').innerHTML=h;
  let m='';[['Source','QRM_STAGING.QUOT (SQL)'],['CurveLabel spread','CAD CDF'],['CurveLabel base','CAD OIS CORRA'],['EvaluationDate',d.EvaluationDate||'—'],['Points',''+rows.length],['Interpolation','Linéaire taux ZC']].forEach(([k,v])=>{m+='<div style="display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid #E5E5EA;font-size:13px"><span style="color:#636366">'+k+'</span><span style="font-weight:600;color:#2C2C2E;font-family:var(--mono);font-size:12px">'+v+'</span></div>'});
  document.getElementById('qcMeta').innerHTML=m;
}

/* TRADES */
function loadTradesFile(i){
  const f=i.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);
  fetch('/cpg/api/upload_trades',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{
    if(d.error){showSt('tradesStatus','⚠ '+d.error,false);tradesOk=false}else{
      showSt('tradesStatus','✓ '+d.count+' trades ('+d.types+')',true);tradesOk=true;
      document.getElementById('tradesBdg').textContent=d.count+' instruments';
      if(d.preview&&d.preview.length){
        document.getElementById('tradesPrevP').style.display='block';
        let h='<table class="results-table"><thead><tr>';
        Object.keys(d.preview[0]).slice(0,8).forEach(k=>h+='<th>'+k+'</th>');
        h+='</tr></thead><tbody>';
        d.preview.forEach(r=>{h+='<tr>';Object.values(r).slice(0,8).forEach(v=>h+='<td>'+v+'</td>');h+='</tr>'});
        h+='</tbody></table>';document.getElementById('tradesPrevB').innerHTML=h;
      }
    }checkReady()
  })
}

/* PRICING */
function runPricing(){
  const btn=document.getElementById('btnRun'),ev=document.getElementById('evalDate').value;
  btn.disabled=true;btn.textContent='⟳ Pricing...';btn.classList.add('running');
  const t0=performance.now();
  fetch('/cpg/api/price',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({eval_date:ev})}).then(r=>r.json()).then(d=>{
    const dt=((performance.now()-t0)/1000).toFixed(1);
    btn.disabled=false;btn.textContent='▶ Pricer';btn.classList.remove('running');
    if(d.error){alert('Erreur: '+d.error);return}
    pricingDone=true;pricingData=d;
    execLog='Pricing: '+dt+'s\n'+d.count_ok+'/'+d.count_total+' OK\nPV total: '+fmt(d.pv_total)+' CAD\n';
    document.getElementById('logArea').textContent=execLog;
    renderSnapshot(d);renderPricing(d);showPage('snapshot');
    computeGreeks();
  }).catch(e=>{btn.disabled=false;btn.textContent='▶ Pricer';btn.classList.remove('running');alert('Erreur: '+e)})
}

/* SNAPSHOT */
function renderSnapshot(d){
  if(!d||!d.results)return;
  const ok=d.results.filter(r=>r.Status==='OK'),tot=ok.reduce((s,r)=>s+(r.PV||0),0),notl=ok.reduce((s,r)=>s+(r.Montant||0),0);
  let h='<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:22px">';
  h+=mkKpi('PV Total',fmtM(tot),'CAD',ok.length+' instruments','var(--green)');
  h+=mkKpi('Notionnel',fmtM(notl),'CAD','Portefeuille CPG','#2C2C2E');
  h+=mkKpi('Duration moy.',fmt(d.avg_duration,2),'ans','Pondérée PV','#007AFF');
  h+=mkKpi('Coupon moy.',fmt(ok.reduce((s,r)=>s+(r.Coupon||0)*(r.Montant||0),0)/notl,2)+' %','','Pondéré notionnel','#5856D6');
  h+=mkKpi('Courbe CDF',curveData?curveData.length:'—','points','','#3A3A3C');
  h+='</div>';

  /* Type breakdown */
  const byType={};ok.forEach(r=>{const t=r.CodeTransaction||r.Type||'?';byType[t]=(byType[t]||0)+(r.PV||0)});
  h+='<div style="display:grid;grid-template-columns:1.3fr 1fr;gap:18px">';
  h+='<div class="panel"><div class="panel-header"><div class="dot"></div>Répartition PV par type</div><div class="panel-body">';
  const colors={'COUPON':'var(--green)','LINEAR ACCRUAL':'#5856D6'};
  Object.entries(byType).forEach(([t,pv])=>{
    const pct=(pv/tot*100);
    h+='<div style="margin-bottom:16px"><div style="display:flex;justify-content:space-between;font-size:13px;margin-bottom:6px"><span style="font-weight:600;color:#2C2C2E">'+t+'</span><span style="font-family:var(--mono);color:#48484A;font-weight:600">'+fmtM(pv)+' $</span></div>';
    h+='<div style="height:8px;background:#E5E5EA;border-radius:4px;overflow:hidden"><div style="height:100%;border-radius:4px;width:'+pct+'%;background:'+(colors[t]||'#8E8E93')+';transition:width .4s"></div></div>';
    h+='<span style="font-size:11px;color:#8E8E93;font-family:var(--mono)">'+fmt(pct,1)+' %</span></div>';
  });
  h+='</div></div>';

  /* Confidence */
  h+='<div class="panel"><div class="panel-header"><div class="dot" style="background:var(--amber)"></div>Confiance pricing</div><div class="panel-body">';
  h+='<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px">';
  [['HIGH','Élevée','#E9F5F0','#CCE7DC','var(--green)'],['MEDIUM','Moyenne','#FFFBF5','#FDE68A','var(--amber)'],['LOW','Faible','#FFF5F5','#FECACA','var(--red)']].forEach(([lv,lb,bg,bd,cl])=>{
    const cnt=ok.filter(r=>(r.Confidence||'MEDIUM')===lv).length;
    h+='<div style="padding:16px;border-radius:12px;text-align:center;background:'+bg+';border:1px solid '+bd+'"><div style="font-size:28px;font-weight:700;font-family:var(--mono);color:'+cl+'">'+cnt+'</div><div style="font-size:12px;font-weight:600;color:#636366;margin-top:4px">Confiance '+lb+'</div></div>';
  });
  h+='</div></div></div></div>';
  document.getElementById('snapshotContent').innerHTML=h;
}

function mkKpi(label,value,unit,sub,color){
  return '<div class="kpi"><div class="kl">'+label+'</div><div style="display:flex;align-items:baseline;gap:4px"><span class="kv" style="color:'+(color||'var(--green)')+'">'+value+'</span>'+(unit?'<span class="ku">'+unit+'</span>':'')+'</div>'+(sub?'<div class="ks">'+sub+'</div>':'')+'</div>';
}

/* PRICING TABLE */
function renderPricing(d){
  if(!d||!d.results)return;
  const ok=d.results.filter(r=>r.Status==='OK'),tot=ok.reduce((s,r)=>s+(r.PV||0),0),notl=ok.reduce((s,r)=>s+(r.Montant||0),0);
  let h='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px">';
  h+=mkKpi('PV Total',fmtM(tot),'CAD','','var(--green)');
  h+=mkKpi('PV Coupons',fmtM(ok.reduce((s,r)=>s+(r.PV_Coupons||0),0)),'CAD','','#007AFF');
  h+=mkKpi('PV Principal',fmtM(ok.reduce((s,r)=>s+(r.PV_Principal||0),0)),'CAD','','#5856D6');
  h+=mkKpi('PV / Notionnel',fmt(tot/notl*100,2)+' %','','','#3A3A3C');
  h+='</div>';
  h+='<div class="panel"><div class="panel-header"><div class="dot"></div>Détail du pricing<span class="bdg bdg-d" style="margin-left:auto">EvalDate: '+document.getElementById('evalDate').value+'</span></div>';
  h+='<div class="panel-body" style="padding:0;overflow-x:auto"><table class="results-table" style="min-width:900px"><thead><tr>';
  ['CUSIP','Type','Montant','Coupon','PV','PV Coupons','PV Principal','DF Mat.','Duration','Status'].forEach(c=>h+='<th style="text-align:'+(['CUSIP','Type','Status'].includes(c)?'left':'right')+'">'+c+'</th>');
  h+='</tr></thead><tbody>';
  ok.forEach((r,i)=>{
    const tp=r.CodeTransaction||r.Type||'?';
    h+='<tr style="background:'+(i%2?'rgba(0,0,0,.01)':'transparent')+'">';
    h+='<td style="font-weight:600;font-family:var(--mono);font-size:11px;color:var(--green)">'+(r.CUSIP||'—')+'</td>';
    h+='<td><span class="bdg '+(tp==='COUPON'?'bdg-g':'bdg-b')+'">'+tp+'</span></td>';
    h+='<td style="text-align:right;font-family:var(--mono)">'+fmtM(r.Montant||0)+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono)">'+fmt(r.Coupon,2)+' %</td>';
    h+='<td style="text-align:right;font-family:var(--mono);font-weight:700;color:var(--green)">'+fmt(r.PV,2)+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono)">'+fmt(r.PV_Coupons,2)+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono)">'+fmt(r.PV_Principal,2)+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono);color:var(--text3)">'+fmt(r.DF_Maturity,6)+'</td>';
    h+='<td style="text-align:right;font-family:var(--mono)">'+fmt(r.Duration,2)+'</td>';
    h+='<td><span class="bdg '+(r.Status==='OK'?'bdg-g':'bdg-r')+'">'+r.Status+'</span></td></tr>';
  });
  h+='</tbody><tfoot><tr style="background:#E9F5F0;font-weight:700"><td colspan="2" style="color:var(--green);padding:12px">TOTAL</td><td style="text-align:right;font-family:var(--mono);padding:12px">'+fmtM(notl)+'</td><td></td><td style="text-align:right;font-family:var(--mono);color:var(--green);font-size:14px;padding:12px">'+fmt(tot,2)+'</td><td colspan="5"></td></tr></tfoot></table></div></div>';
  document.getElementById('pricingContent').innerHTML=h;
}

/* GREEKS (server-side) */
function computeGreeks(){
  const el=document.getElementById('riskContent');
  el.innerHTML='<div class="wempty"><div style="width:24px;height:24px;border:2px solid rgba(0,0,0,.06);border-top-color:var(--accent);border-radius:50%;animation:spin .7s linear infinite;display:inline-block;margin-bottom:8px"></div><p>Calcul des Greeks en cours...</p></div>';
  fetch('/cpg/api/greeks',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({eval_date:document.getElementById('evalDate').value,bump_bp:1.0})}).then(r=>r.json()).then(g=>{
    if(g.error){el.innerHTML='<div class="panel"><div class="panel-body" style="color:var(--red)">⚠ '+g.error+'</div></div>';return}
    renderRisk(g);execLog+='Greeks: DV01='+fmt(g.dv01.DV01)+', Gamma='+fmt(g.gamma.Gamma_1bp)+'\n';document.getElementById('logArea').textContent=execLog;
  }).catch(e=>{el.innerHTML='<div class="panel"><div class="panel-body" style="color:var(--red)">Erreur: '+e+'</div></div>'})
}

function renderRisk(g){
  const pv=g.PV_base;
  let h='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px">';
  h+=mkKpi('DV01',fmt(g.dv01.DV01),'$/bp','Exact (repricing ±1bp)','#FF3B30');
  h+=mkKpi('Gamma (1bp)',fmt(g.gamma.Gamma_1bp),'$/bp²','Convexité','#5856D6');
  h+=mkKpi('Theta (1j)',fmt(g.theta.Theta_1d),'$','Carry 1 jour','#007AFF');
  h+=mkKpi('Vega (1bp)',fmt(g.vega.Vega_1bp),'$',g.vega.source,'#FF9500');
  h+='</div>';

  if(g.vega.note){h+='<div style="font-size:11px;color:var(--text3);margin-bottom:16px;padding:8px 12px;background:var(--bg);border-radius:6px;border-left:3px solid var(--amber)">'+g.vega.note+' <span class="bdg bdg-a" style="margin-left:4px">'+g.vega.confidence+'</span></div>'}

  /* Key Rate DV01 */
  h+='<div class="panel" style="margin-bottom:18px"><div class="panel-header"><div class="dot" style="background:#FF3B30"></div>Key Rate DV01 (par bucket)</div><div class="panel-body" style="padding:0"><table class="results-table"><thead><tr><th>Bucket</th><th style="text-align:right">DV01</th><th style="text-align:right">% total</th><th>Distribution</th></tr></thead><tbody>';
  const totKR=Object.values(g.key_rate_dv01).reduce((s,v)=>s+Math.abs(v),0);
  Object.entries(g.key_rate_dv01).forEach(([k,v])=>{
    const pct=totKR>0?(Math.abs(v)/totKR*100):0;
    h+='<tr><td class="name">'+k+'</td><td style="text-align:right;font-weight:600">'+fmt(v)+'</td><td style="text-align:right">'+fmt(pct,1)+' %</td><td><div class="krbar"><div class="krbar-f" style="width:'+Math.min(pct,100)+'%"></div></div></td></tr>';
  });
  h+='</tbody></table></div></div>';

  /* Scenarios */
  h+='<div class="panel"><div class="panel-header"><div class="dot" style="background:var(--amber)"></div>Scénarios de taux</div><div class="panel-body" style="padding:0"><table class="results-table"><thead><tr><th>Scénario</th><th>Type</th><th style="text-align:right">PV</th><th style="text-align:right">ΔPV</th><th style="text-align:right">Δ%</th></tr></thead><tbody>';
  g.scenarios.forEach(s=>{
    const cls=s.delta_PV>0?'diff-good':s.delta_PV<0?'diff-bad':'';
    h+='<tr><td class="name">'+s.scenario+'</td><td style="font-size:11px;color:var(--text3)">'+s.type+'</td><td style="text-align:right;font-weight:600">'+fmt(s.PV)+'</td><td style="text-align:right" class="'+cls+'">'+(s.delta_PV>=0?'+':'')+fmt(s.delta_PV)+'</td><td style="text-align:right" class="'+cls+'">'+(s.delta_pct>=0?'+':'')+fmt(s.delta_pct,3)+' %</td></tr>';
  });
  h+='</tbody></table></div></div>';
  h+='<div style="font-size:11px;color:var(--text3);margin-top:12px">DV01/Gamma par repricing exact ±1bp. Scénarios: parallèles + twist. Vol: '+g.vol_source+'</div>';
  document.getElementById('riskContent').innerHTML=h;
}

/* VOL */
function loadVolFile(i){
  const f=i.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);
  fetch('/cpg/api/vol/upload',{method:'POST',body:fd}).then(r=>r.json()).then(d=>{
    if(d.error){showSt('volStatus','⚠ '+d.error,false);return}
    showSt('volStatus','✓ '+d.points+' pts · Source: '+d.source,true);volMode=1;renderVolHeatmap(d);
  })
}
function applyVolProxy(){
  const p={vol_base:+document.getElementById('volBase').value,slope:+document.getElementById('volSlope').value,floor:+document.getElementById('volFloor').value};
  fetch('/cpg/api/vol/proxy',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)}).then(r=>r.json()).then(d=>{if(!d.error)renderVolHeatmap(d)})
}
function renderVolHeatmap(d){
  if(!d.vol_matrix||!d.vol_matrix.length)return;
  let h='<div style="overflow-x:auto"><table class="results-table" style="font-size:10px"><thead><tr><th>Expiry\\Tenor</th>';
  d.tenor_grid.forEach(t=>{h+='<th style="text-align:right">'+t.toFixed(1)+'Y</th>'});h+='</tr></thead><tbody>';
  const flat=d.vol_matrix.flat(),vMin=Math.min(...flat),vMax=Math.max(...flat);
  d.vol_matrix.forEach((row,i)=>{
    h+='<tr><td class="name">'+d.expiry_grid[i].toFixed(2)+'Y</td>';
    row.forEach(v=>{const p=(v-vMin)/(vMax-vMin||1);const r=Math.round(255*(1-p)),g=Math.round(200+55*p),b=Math.round(200*(1-p));h+='<td style="text-align:right;background:rgba('+r+','+g+','+b+',.15);font-weight:600">'+v.toFixed(1)+'</td>'});
    h+='</tr>';
  });h+='</tbody></table></div>';
  document.getElementById('volHeatArea').innerHTML=h;
}

/* INIT */
checkReady();setTimeout(applyVolProxy,200);
</script>

"""

# ═══════════════════════════════════════════════════════════════════════════
#  PAGE ASSEMBLY — each tool is fully self-contained
# ═══════════════════════════════════════════════════════════════════════════

def _page(title, active, body, extra_right=""):
    """Assemble a complete HTML page from shared head + header + body."""
    return (
        f"<!DOCTYPE html><html lang='fr'><head>{SHARED_HEAD}"
        f"<title>{title}</title></head><body>"
        f"{_header_html(active, extra_right)}"
        f"{body}</body></html>"
    )


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES — BERMUDAN SWAPTION PRICER
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    badge = '<div style="font-size:11px;font-family:var(--mono);padding:5px 14px;border-radius:99px;background:var(--green-bg);color:var(--green);border:1px solid rgba(0,135,78,0.15);font-weight:600" id="statusBadge">READY</div>'
    return _page("Bermudan Swaption Pricer — Desjardins", "bermudan", BERMUDAN_BODY, badge)


@app.route("/api/upload_excel", methods=["POST"])
def api_upload_excel():
    try:
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "No file uploaded"})
        tmp = os.path.join(tempfile.gettempdir(), "mkt_data.xlsx")
        f.save(tmp)
        wb = openpyxl.load_workbook(tmp, data_only=True)
        result = {}
        # Curve sheet
        curve_sheet = None
        for name in wb.sheetnames:
            if "curve" in name.lower() or "ois" in name.lower():
                curve_sheet = name
                break
        if not curve_sheet:
            curve_sheet = wb.sheetnames[0]
        ws = wb[curve_sheet]
        curve_data = []
        # Auto-detect columns
        header = [str(c.value or "").strip().lower() for c in ws[1]]
        date_col = 0
        df_col = 1
        for i, h in enumerate(header):
            if "date" in h:
                date_col = i
            if "discount" in h or h == "df":
                df_col = i
        all_rows = list(ws.iter_rows(min_row=2, values_only=True))
        if all_rows and df_col == 1:
            try:
                test_val = float(all_rows[0][1])
                if test_val > 1.0:
                    for ci in range(len(all_rows[0])):
                        try:
                            tv = float(all_rows[0][ci])
                            if 0 < tv < 1.0:
                                df_col = ci
                                break
                        except:
                            pass
            except:
                pass
        for row in all_rows:
            if row[date_col] is None:
                continue
            d = row[date_col]
            d = d.strftime("%Y-%m-%d") if isinstance(d, datetime) else str(d).strip().split()[0]
            try:
                curve_data.append([d, float(row[df_col])])
            except:
                continue
        result["curve"] = curve_data
        # Vol sheet
        vol_sheet = None
        for name in wb.sheetnames:
            if "vol" in name.lower() or "bvol" in name.lower():
                vol_sheet = name
                break
        if not vol_sheet and len(wb.sheetnames) > 1:
            vol_sheet = wb.sheetnames[1]
        if vol_sheet:
            ws = wb[vol_sheet]
            rows = list(ws.iter_rows(values_only=True))
            tenor_labels = [str(c).strip() for c in rows[0][1:] if c is not None]
            expiry_labels = []
            vol_values = []
            for row in rows[1:]:
                if row[0] is None:
                    continue
                expiry_labels.append(str(row[0]).strip())
                vol_values.append([float(c) if c else 0.0 for c in row[1:1+len(tenor_labels)]])
            result["vol_values"] = vol_values
            result["expiry_labels"] = expiry_labels
            result["tenor_labels"] = tenor_labels
        wb.close()
        return jsonify(result)
    except Exception as e:
        import traceback
        return jsonify({"error": f"{e}\n{traceback.format_exc()}"})


@app.route("/api/price", methods=["POST"])
def api_price():
    try:
        cfg = request.json
        vol_values = np.array(cfg.get("vol_surface_data", {}).get("values", []), dtype=float)
        from bbg_fetcher import labels_to_years, EXPIRY_LABEL_TO_YEARS, TENOR_LABEL_TO_YEARS
        exp_labels = cfg.get("vol_surface_data", {}).get("expiry_labels", [])
        tnr_labels = cfg.get("vol_surface_data", {}).get("tenor_labels", [])
        market_data = {
            "curve": cfg.get("curve_data", []),
            "vol_surface": vol_values,
            "expiry_grid": labels_to_years(exp_labels, EXPIRY_LABEL_TO_YEARS),
            "tenor_grid": labels_to_years(tnr_labels, TENOR_LABEL_TO_YEARS),
            "bbg_npv": float(cfg.get("benchmark", {}).get("npv", 0)),
        }
        log_buf = io.StringIO()
        with redirect_stdout(log_buf):
            from pricer import BermudanPricer
            pricer = BermudanPricer(cfg, market_data)
            pricer.setup()
            pricer.calibrate()
            pricer.compute_greeks()
        bps_leg = abs(float(pricer.swap.fixedLegBPS()))
        yv = pricer.npv / bps_leg if bps_leg else 0
        app.config["LAST_PRICER"] = pricer
        app.config["LAST_CFG"] = cfg
        return jsonify({
            "npv": pricer.npv, "sigma_atm": pricer.sigma_atm,
            "sigma_total": pricer.sigma_total, "delta_spread": pricer.delta_spread,
            "fair_rate": pricer.fair_rate, "underlying_npv": pricer.underlying_npv,
            "yield_value": yv, "premium_pct": pricer.npv / pricer.notional * 100,
            "underlying_prem_pct": pricer.underlying_npv / pricer.notional * 100,
            "moneyness_bp": (pricer.strike - pricer.fair_rate) * 10000,
            "greeks": pricer.greeks,
            "a_used": pricer.a, "a_calibrated": pricer.calib_a,
            "log": log_buf.getvalue(),
        })
    except Exception as e:
        import traceback
        return jsonify({"error": f"{e}\n\n{traceback.format_exc()}"})


@app.route("/api/export")
def api_export():
    pricer = app.config.get("LAST_PRICER")
    if not pricer:
        return "No results. Run pricer first.", 400
    xlsx = os.path.join(tempfile.gettempdir(), "bermudan_results.xlsx")
    pricer.export_excel(xlsx)
    return send_file(xlsx, as_attachment=True, download_name="bermudan_results.xlsx")


@app.route("/api/export_pbi")
def api_export_pbi():
    """Export structured Excel optimized for Power BI."""
    pricer = app.config.get("LAST_PRICER")
    cfg = app.config.get("LAST_CFG")
    if not pricer:
        return "No results. Run pricer first.", 400
    try:
        from run_and_export import export_pbi_excel
        xlsx = os.path.join(tempfile.gettempdir(), "pbi_data.xlsx")
        export_pbi_excel(pricer, cfg, xlsx)
        return send_file(xlsx, as_attachment=True, download_name="pbi_data.xlsx")
    except Exception as e:
        import traceback
        return str(e) + "\n" + traceback.format_exc(), 500


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES — CPG PORTFOLIO PRICER (fully isolated from Bermudan)
# ═══════════════════════════════════════════════════════════════════════════

@app.route("/cpg")
def cpg_index():
    # CPG workspace has its own sidebar + topbar, so skip the shared header
    return (
        f"<!DOCTYPE html><html lang='fr'><head>{SHARED_HEAD}"
        f"<title>CPG Portfolio Pricer — Desjardins</title></head><body style='margin:0;padding:0'>"
        f"{CPG_BODY}</body></html>"
    )


@app.route("/cpg/api/upload_curve", methods=["POST"])
def cpg_upload_curve():
    try:
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "Aucun fichier"})
        import pandas as pd
        tmp = os.path.join(tempfile.gettempdir(), "cpg_curve.csv")
        f.save(tmp)
        from cpg.curve_sql import load_curve_from_csv
        df = load_curve_from_csv(tmp)
        app.config["CPG_CURVE"] = df
        rng = f"{df['ApproxDays'].min()}j – {df['ApproxDays'].max()}j"
        # Build preview rows
        preview = []
        for _, r in df.iterrows():
            preview.append({
                "termPoint": int(r["termPoint"]),
                "termType": r["termType"],
                "ZeroCouponSpreadCDF": round(float(r["ZeroCouponSpreadCDF"]), 6) if "ZeroCouponSpreadCDF" in r and pd.notna(r.get("ZeroCouponSpreadCDF")) else None,
                "ZeroCouponBase": round(float(r["ZeroCouponBase"]), 6) if "ZeroCouponBase" in r and pd.notna(r.get("ZeroCouponBase")) else None,
                "TauxCDF": round(float(r["TauxCDF"]), 6),
                "ApproxDays": int(r["ApproxDays"]),
            })
        return jsonify({"points": len(df), "range": rng, "preview": preview})
    except Exception as e:
        return jsonify({"error": str(e)})


# ─────────────────────────────────────────────────────────────────────────────
# CPG — Fetch CAD CDF (spread) + CAD OIS CORRA (base) depuis QRM_STAGING.QUOT
# Sortie normalisée: termPoint, termType, ZeroCouponSpreadCDF, ZeroCouponBase,
#                    TauxCDF (= Base + Spread), ApproxDays
# ─────────────────────────────────────────────────────────────────────────────


@app.route("/cpg/api/fetch_curve_cdf", methods=["POST"])
def cpg_fetch_curve_cdf():
    """
    Récupère la courbe CDF en combinant:
      - A: CAD CDF (ZeroCoupon -> spread)
      - B: CAD OIS CORRA (ZeroCoupon -> base)
    au dernier EvaluationDate disponible <= eval_date (si fourni), sinon dernier disponible.
    Source: [BD_ET_QRM_Staging].[dbo].[QRM_MUREX_YIELD_CURVE_QUOT]
    """
    try:
        import pandas as pd
        import numpy as np
        from datetime import datetime, date

        data = request.json or {}
        eval_date_str = (data.get("eval_date") or "").strip()

        cutoff = None
        if eval_date_str:
            try:
                cutoff = datetime.strptime(eval_date_str, "%Y-%m-%d").date()
            except ValueError:
                return jsonify({"error": "Format de 'eval_date' invalide (attendu YYYY-MM-DD)."}), 400

        server   = "MSSQL-DOT.Desjardins.com"
        database = "BD_ET_QRM_Staging"
        engine = create_engine(
            f"mssql+pyodbc://@{server}/{database}"
            f"?driver=ODBC+Driver+17+for+SQL+Server&trusted_connection=yes"
        )

        sql_with_cutoff = text("""
WITH latest AS (
    SELECT MAX(EvaluationDate) AS EvaluationDate
    FROM [BD_ET_QRM_Staging].[dbo].[QRM_MUREX_YIELD_CURVE_QUOT]
    WHERE EvaluationDate <= :cutoff
      AND CurveLabel IN ('CAD CDF','CAD OIS CORRA')
)
SELECT
    A.EvaluationDate, A.CurveLabel, A.termPoint, A.termType,
    A.ZeroCoupon AS ZeroCouponSpreadCDF,
    B.ZeroCoupon AS ZeroCouponBase,
    (A.ZeroCoupon + B.ZeroCoupon) AS TauxCDF,
    A.NbrJoursQRM
FROM [BD_ET_QRM_Staging].[dbo].[QRM_MUREX_YIELD_CURVE_QUOT] AS A
LEFT JOIN [BD_ET_QRM_Staging].[dbo].[QRM_MUREX_YIELD_CURVE_QUOT] AS B
    ON  B.CurveLabel     = 'CAD OIS CORRA'
    AND B.termPoint      = A.termPoint
    AND B.termType       = A.termType
    AND B.EvaluationDate = (SELECT EvaluationDate FROM latest)
WHERE A.CurveLabel     = 'CAD CDF'
  AND A.EvaluationDate = (SELECT EvaluationDate FROM latest)
ORDER BY A.NbrJoursQRM;
""")

        sql_no_cutoff = text("""
WITH latest AS (
    SELECT MAX(EvaluationDate) AS EvaluationDate
    FROM [BD_ET_QRM_Staging].[dbo].[QRM_MUREX_YIELD_CURVE_QUOT]
    WHERE CurveLabel IN ('CAD CDF','CAD OIS CORRA')
)
SELECT
    A.EvaluationDate, A.CurveLabel, A.termPoint, A.termType,
    A.ZeroCoupon AS ZeroCouponSpreadCDF,
    B.ZeroCoupon AS ZeroCouponBase,
    (A.ZeroCoupon + B.ZeroCoupon) AS TauxCDF,
    A.NbrJoursQRM
FROM [BD_ET_QRM_Staging].[dbo].[QRM_MUREX_YIELD_CURVE_QUOT] AS A
LEFT JOIN [BD_ET_QRM_Staging].[dbo].[QRM_MUREX_YIELD_CURVE_QUOT] AS B
    ON  B.CurveLabel     = 'CAD OIS CORRA'
    AND B.termPoint      = A.termPoint
    AND B.termType       = A.termType
    AND B.EvaluationDate = (SELECT EvaluationDate FROM latest)
WHERE A.CurveLabel     = 'CAD CDF'
  AND A.EvaluationDate = (SELECT EvaluationDate FROM latest)
ORDER BY A.NbrJoursQRM;
""")

        with engine.begin() as conn:
            if cutoff:
                df = pd.read_sql_query(sql_with_cutoff, conn, params={"cutoff": cutoff})
            else:
                df = pd.read_sql_query(sql_no_cutoff, conn)

        if df.empty:
            msg = f"Aucune donnée trouvée (<= {cutoff})" if cutoff else "Aucune donnée trouvée (aucune date disponible)"
            return jsonify({"error": msg}), 404

        out = pd.DataFrame({
            "termPoint":           df["termPoint"].astype(int),
            "termType":            df["termType"].astype(str),
            "ZeroCouponSpreadCDF": df["ZeroCouponSpreadCDF"].astype(float),
            "ZeroCouponBase":      df["ZeroCouponBase"].astype(float),
            "TauxCDF":             df["TauxCDF"].astype(float),
            "ApproxDays":          (df["NbrJoursQRM"] if "NbrJoursQRM" in df else np.nan),
        })

        if out["ApproxDays"].isna().any():
            factor = {"Day": 1, "Week": 7, "Month": 30, "Year": 365,
                      "Jour": 1, "Semaine": 7, "Mois": 30, "Année": 365, "An": 365}
            out["ApproxDays"] = out.apply(
                lambda r: int(r["termPoint"]) * factor.get(str(r["termType"]).strip(), 30),
                axis=1
            ).astype(int)
        else:
            out["ApproxDays"] = out["ApproxDays"].astype(int)

        out = out.sort_values("ApproxDays").reset_index(drop=True)

        used_eval = df["EvaluationDate"].iloc[0]
        used_eval_str = used_eval.strftime("%Y-%m-%d") if hasattr(used_eval, "strftime") else str(used_eval)
        app.config["CPG_CURVE"] = out

        rng = f"{int(out['ApproxDays'].min())}j \u2013 {int(out['ApproxDays'].max())}j"
        preview = [{
            "termPoint": int(r.termPoint),
            "termType": str(r.termType),
            "ZeroCouponSpreadCDF": round(float(r.ZeroCouponSpreadCDF), 6),
            "ZeroCouponBase": round(float(r.ZeroCouponBase), 6),
            "TauxCDF": round(float(r.TauxCDF), 6),
            "ApproxDays": int(r.ApproxDays),
        } for _, r in out.iterrows()]

        return jsonify({
            "points": int(len(out)),
            "range": rng,
            "preview": preview,
            "EvaluationDate": used_eval_str
        })

    except Exception as e:
        import traceback
        return jsonify({"error": f"{e}\n{traceback.format_exc()}"}), 500



@app.route("/cpg/api/upload_trades", methods=["POST"])
def cpg_upload_trades():
    try:
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "Aucun fichier"})
        ext = os.path.splitext(f.filename)[1].lower()
        tmp = os.path.join(tempfile.gettempdir(), "cpg_trades" + ext)
        f.save(tmp)
        from cpg.trades import load_trades_file
        df = load_trades_file(tmp)
        app.config["CPG_TRADES"] = df
        types = ", ".join(f"{k}:{v}" for k, v in df["CodeTransaction"].value_counts().items())
        return jsonify({"count": len(df), "types": types})
    except Exception as e:
        return jsonify({"error": str(e)})



@app.route("/cpg/api/download_trades_template")
def cpg_download_trades_template():
    import pandas as pd
    cols = ["CodeTransaction","Inventaire","Contrepartie","DateÉmission","DateEcheanceInitial",
            "DateEcheanceFinal","Montant","Coupon","Marge","Frequence","BaseCalcul",
            "Devise","CUSIP","FundServ"]
    sample = [
        ["COUPON","PRORO","418414","2025-12-19","2026-12-19","2035-12-19"," 1,000.00  $ ","5.00%","0.00%","Annuel","ACT/365","CAD","CA31430XKX98","DSN12345"],
        ["COUPON","PRORO","418414","2025-11-19","2026-11-19","2035-11-19"," 1,000.00  $ ","4.50%","0.00%","Annuel","ACT/365","CAD","CA31430XKK77","DSN12345"],
        ["LINEAR ACCRUAL","PRORO","418414","2025-12-19","2040-12-19","2040-12-19"," 1,000.00  $ ","6.00%","0.00%","Maturité","ACT/365","CAD","CA31393ZGQ96","DSN12345"],
    ]
    df = pd.DataFrame(sample, columns=cols)
    tmp = os.path.join(tempfile.gettempdir(), "trades_template.xlsx")
    df.to_excel(tmp, index=False, engine="openpyxl")
    return send_file(tmp, as_attachment=True, download_name="trades_template.xlsx")


@app.route("/cpg/api/price", methods=["POST"])
def cpg_price():
    try:
        import pandas as pd
        curve_df = app.config.get("CPG_CURVE")
        trades_df = app.config.get("CPG_TRADES")
        if curve_df is None:
            return jsonify({"error": "Courbe non chargée"})
        if trades_df is None:
            return jsonify({"error": "Trades non chargés"})
        eval_date = request.json.get("eval_date", "2026-02-26")
        from cpg.pricing import price_cpg_portfolio
        results = price_cpg_portfolio(trades_df, curve_df, eval_date)
        app.config["CPG_RESULTS"] = results
        ok = results[results["Status"] == "OK"]
        # Serialize dates for JSON
        rows = results.copy()
        for c in ["DateEmission", "DateEcheanceFinal"]:
            if c in rows.columns:
                rows[c] = rows[c].apply(lambda x: x.strftime("%Y-%m-%d") if hasattr(x, "strftime") else str(x))
        return jsonify({
            "count_total": len(results),
            "count_ok": len(ok),
            "pv_total": round(ok["PV"].sum(), 2),
            "notional_total": round(ok["Montant"].sum(), 2),
            "avg_duration": round((ok["Duration_Approx"] * ok["PV"]).sum() / ok["PV"].sum(), 4) if ok["PV"].sum() > 0 else 0,
            "results": rows.drop(columns=["Cashflows"], errors="ignore").to_dict(orient="records"),
        })
    except Exception as e:
        import traceback
        return jsonify({"error": f"{e}\n{traceback.format_exc()}"})


@app.route("/cpg/api/export")
def cpg_export():
    results = app.config.get("CPG_RESULTS")
    if results is None:
        return "Aucun résultat. Lancer le pricing d'abord.", 400
    from cpg.export import export_results
    tmp = os.path.join(tempfile.gettempdir(), "cpg_results.xlsx")
    export_results(results, tmp)
    return send_file(tmp, as_attachment=True, download_name="cpg_results.xlsx")


# ═══════════════════════════════════════════════════════════════════════════
#  ROUTES — CPG Risk Analytics (Greeks, Vol, Scenarios)
# ═══════════════════════════════════════════════════════════════════════════


@app.route("/cpg/api/greeks", methods=["POST"])
def cpg_greeks():
    """Compute full risk analytics: DV01, Gamma, KR-DV01, Theta, Vega, Scenarios."""
    try:
        curve_df = app.config.get("CPG_CURVE")
        trades_df = app.config.get("CPG_TRADES")
        if curve_df is None:
            return jsonify({"error": "Courbe non chargée"})
        if trades_df is None:
            return jsonify({"error": "Trades non chargés"})

        data = request.json or {}
        eval_date = data.get("eval_date", "2026-02-26")
        bump_bp = float(data.get("bump_bp", 1.0))

        from cpg.greeks import compute_all_greeks
        vol_connector = app.config.get("CPG_VOL_CONNECTOR")

        result = compute_all_greeks(
            trades_df, curve_df, eval_date,
            vol_connector=vol_connector,
            bump_bp=bump_bp,
        )

        app.config["CPG_GREEKS"] = result
        return jsonify(result)

    except Exception as e:
        import traceback
        return jsonify({"error": f"{e}\n{traceback.format_exc()}"}), 500


@app.route("/cpg/api/vol/upload", methods=["POST"])
def cpg_vol_upload():
    """Upload a vol surface (CSV/Excel) — explicit vol mode."""
    try:
        f = request.files.get("file")
        if not f:
            return jsonify({"error": "Aucun fichier"})

        ext = os.path.splitext(f.filename)[1].lower()
        tmp = os.path.join(tempfile.gettempdir(), "cpg_vol" + ext)
        f.save(tmp)

        from cpg.bloomberg import BloombergConnector
        bbg = BloombergConnector(mode="file")
        df = bbg.load_vol_surface(tmp)
        app.config["CPG_VOL_CONNECTOR"] = bbg

        matrix = bbg.get_vol_matrix()
        return jsonify({
            "points": len(df),
            "source": bbg.vol_source,
            "as_of": bbg.vol_as_of,
            "expiry_grid": matrix["expiry_grid"],
            "tenor_grid": matrix["tenor_grid"],
            "vol_matrix": matrix["vol_matrix"],
        })

    except Exception as e:
        import traceback
        return jsonify({"error": f"{e}\n{traceback.format_exc()}"}), 500


@app.route("/cpg/api/vol/proxy", methods=["POST"])
def cpg_vol_proxy():
    """Generate a proxy vol surface from parameters."""
    try:
        data = request.json or {}
        from cpg.bloomberg import BloombergConnector
        bbg = BloombergConnector(mode="file")
        df = bbg.generate_proxy_surface(
            vol_base_bp=float(data.get("vol_base", 65)),
            slope_per_year=float(data.get("slope", -2)),
            floor_bp=float(data.get("floor", 30)),
            smile_curvature=float(data.get("smile", 0)),
        )
        app.config["CPG_VOL_CONNECTOR"] = bbg

        matrix = bbg.get_vol_matrix()
        return jsonify({
            "points": len(df),
            "source": bbg.vol_source,
            "as_of": bbg.vol_as_of,
            "expiry_grid": matrix["expiry_grid"],
            "tenor_grid": matrix["tenor_grid"],
            "vol_matrix": matrix["vol_matrix"],
        })

    except Exception as e:
        import traceback
        return jsonify({"error": f"{e}\n{traceback.format_exc()}"}), 500


@app.route("/cpg/api/vol/status")
def cpg_vol_status():
    """Return current vol surface status."""
    bbg = app.config.get("CPG_VOL_CONNECTOR")
    if bbg is None or not bbg.has_vol:
        return jsonify({"loaded": False, "source": "none"})

    matrix = bbg.get_vol_matrix()
    return jsonify({
        "loaded": True,
        "source": bbg.vol_source,
        "as_of": bbg.vol_as_of,
        "expiry_count": len(matrix["expiry_grid"]),
        "tenor_count": len(matrix["tenor_grid"]),
    })


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN — startup
# ═══════════════════════════════════════════════════════════════════════════

def open_browser():
    webbrowser.open("http://localhost:5000")


if __name__ == "__main__":
    print("=" * 64)
    print("  Desjardins Analytics — Portail de pricing")
    print("  http://localhost:5000          Bermudan Swaption")
    print("  http://localhost:5000/cpg      CPG Portfolio")
    print("=" * 64)
    print("  Ctrl+C pour arrêter\n")
    threading.Timer(1.5, open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False)
