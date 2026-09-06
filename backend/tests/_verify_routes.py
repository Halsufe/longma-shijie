from backend.app.main import app

routes = [r for r in app.routes if hasattr(r, "methods") and hasattr(r, "path")]
print(f"Total routes: {len(routes)}")
keywords = ["course", "assignment", "notification", "skill", "mcp", "audit", "stats", "config", "submission", "schedule"]
print("--- P5-P7 new routes ---")
for r in routes:
    if any(k in r.path for k in keywords):
        methods = sorted(r.methods - {"HEAD"})
        print(f"  {methods[-1]:6s} {r.path}")
print("--- skill seed check ---")
from backend.app.core.database import SessionLocal
from backend.app.repositories.skill_repo import SkillRepository
db = SessionLocal()
skills = SkillRepository.list(db)
print(f"System skills seeded: {len(skills)} -> {[s.name for s in skills]}")
db.close()
