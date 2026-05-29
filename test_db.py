import db
import traceback
try:
    print("Testing create_ticket")
    res = db.create_ticket("TEST_01", "Test Subject", "Test User", "Form 1", {"test": "data"})
    print("Result:", res)
except Exception as e:
    print("Exception:")
    traceback.print_exc()
