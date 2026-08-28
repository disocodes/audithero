from pathlib import Path

def find_project_root(start=None):
    here=Path(start or Path.cwd()).resolve()
    for p in [here,*here.parents]:
        if (p/'databricks.yml').exists() and (p/'rules').exists(): return p
    raise FileNotFoundError('Could not locate AuditHero project root.')
