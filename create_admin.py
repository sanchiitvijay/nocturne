#!/usr/bin/env python3
"""Create a new admin user account."""
import sys
from app import db, security

def create_admin(username: str, password: str) -> bool:
    """Create a new admin user. Returns True if successful."""
    # Validate password
    problem = security.password_problem(password)
    if problem:
        print(f"❌ Password problem: {problem}")
        return False

    with db.session() as conn:
        # Check if user already exists
        existing = db.one(conn, "SELECT id FROM users WHERE username = ?", (username,))
        if existing:
            print(f"❌ User '{username}' already exists")
            return False

        # Create the user
        try:
            conn.execute(
                "INSERT INTO users(username, display_name, password_hash, role, active, must_change, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (username, f"Admin ({username})", security.hash_password(password), "admin", 1, 0, db.now())
            )
            db.audit(conn, None, "user.create", username)
            print(f"✅ Admin user '{username}' created successfully!")
            return True
        except Exception as e:
            print(f"❌ Error creating user: {e}")
            return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <username> <password>")
        sys.exit(1)

    username = sys.argv[1]
    password = sys.argv[2]

    db.init()
    success = create_admin(username, password)
    sys.exit(0 if success else 1)
