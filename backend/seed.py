import sys
from pathlib import Path

# Add backend directory to sys.path to allow imports
sys.path.append(str(Path(__file__).resolve().parent))

from app.database import SessionLocal, engine
from app.models.hcp import HCP

def seed_db():
    print("Checking database for seeding...")
    db = SessionLocal()
    try:
        # Check if we already have HCPs
        existing_count = db.query(HCP).count()
        if existing_count > 0:
            print(f"Database already seeded with {existing_count} HCPs. Skipping.")
            return

        print("No HCPs found. Seeding initial Healthcare Professionals (HCPs)...")
        mock_hcps = [
            HCP(name="Dr. Amit Sharma", hospital="Apollo Hospital", specialization="Cardiology", city="Mumbai"),
            HCP(name="Dr. Priya Patel", hospital="Lilavati Hospital", specialization="Pediatrics", city="Mumbai"),
            HCP(name="Dr. Rajesh Kumar", hospital="Max Super Speciality Hospital", specialization="Oncology", city="Delhi"),
            HCP(name="Dr. Sneha Reddy", hospital="Fortis Hospital", specialization="Neurology", city="Bangalore"),
            HCP(name="Dr. Vikram Malhotra", hospital="Medanta The Medicity", specialization="Endocrinology", city="Gurugram")
        ]
        
        db.add_all(mock_hcps)
        db.commit()
        print(f"Successfully seeded {len(mock_hcps)} Healthcare Professionals (HCPs) into the database.")
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_db()
