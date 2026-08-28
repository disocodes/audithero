# Databricks notebook source
from pathlib import Path
import sys
ROOT=next((p for p in [Path.cwd().resolve(),*Path.cwd().resolve().parents] if (p/'databricks.yml').exists()),None)
if ROOT is None:raise RuntimeError('AuditHero root not found')
if str(ROOT/'src') not in sys.path:sys.path.insert(0,str(ROOT/'src'))
