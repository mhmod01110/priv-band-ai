#!/usr/bin/env python3
"""
RabbitMQ + MongoDB Celery Setup Test
Tests broker connection, result backend, and task execution
"""
import sys
import time
from datetime import datetime
from celery import Celery
from pymongo import MongoClient


def print_step(step_num, message):
    """Print test step"""
    print(f"\n{'='*60}")
    print(f"Step {step_num}: {message}")
    print('='*60)


def print_success(message):
    """Print success message"""
    print(f"✅ {message}")


def print_error(message):
    """Print error message"""
    print(f"❌ {message}")


def print_info(message):
    """Print info message"""
    print(f"ℹ️  {message}")


def test_rabbitmq_connection():
    """Test RabbitMQ connection"""
    print_step(1, "Testing RabbitMQ Connection")
    
    try:
        app = Celery(broker='amqp://guest:guest@localhost:5672//')
        
        # Try to establish connection
        with app.connection() as conn:
            conn.connect()
            print_success("RabbitMQ connection successful")
            print_info(f"Broker URL: amqp://guest:***@localhost:5672//")
            return True
    except Exception as e:
        print_error(f"RabbitMQ connection failed: {str(e)}")
        print_info("Make sure RabbitMQ is running: sudo systemctl status rabbitmq-server")
        return False


def test_mongodb_connection():
    """Test MongoDB connection"""
    print_step(2, "Testing MongoDB Connection")
    
    try:
        client = MongoClient('mongodb://localhost:27017/', serverSelectionTimeoutMS=5000)
        
        # Test connection
        client.admin.command('ping')
        
        # Get database
        db = client['legal_policy_analyzer']
        
        print_success("MongoDB connection successful")
        print_info(f"Database: legal_policy_analyzer")
        
        # List collections
        collections = db.list_collection_names()
        print_info(f"Collections: {', '.join(collections) if collections else 'None yet'}")
        
        return True
    except Exception as e:
        print_error(f"MongoDB connection failed: {str(e)}")
        print_info("Make sure MongoDB is running: sudo systemctl status mongod")
        return False


def test_celery_task():
    """Test Celery task execution"""
    print_step(3, "Testing Celery Task Execution")
    
    # Create Celery app
    app = Celery(
        'test',
        broker='amqp://guest:guest@localhost:5672//',
        backend='mongodb://localhost:27017/legal_policy_analyzer'
    )
    
    app.conf.update(
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        mongodb_backend_settings={
            'database': 'legal_policy_analyzer',
            'taskmeta_collection': 'celery_taskmeta',
        }
    )
    
    @app.task(name='test.add')
    def add(x, y):
        """Simple test task"""
        return x + y
    
    try:
        print_info("Sending test task (add 5 + 3)...")
        
        # Send task
        result = add.apply_async(args=[5, 3])
        
        print_success(f"Task submitted successfully")
        print_info(f"Task ID: {result.id}")
        
        # Wait for result (with timeout)
        print_info("Waiting for result (timeout: 10 seconds)...")
        
        try:
            task_result = result.get(timeout=10)
            print_success(f"Task completed! Result: {task_result}")
            
            # Verify result
            if task_result == 8:
                print_success("Result is correct (5 + 3 = 8)")
                return True
            else:
                print_error(f"Result is incorrect. Expected 8, got {task_result}")
                return False
                
        except Exception as e:
            print_error(f"Task execution failed or timed out: {str(e)}")
            print_info("Make sure Celery worker is running:")
            print_info("  celery -A test_rabbitmq_setup worker --loglevel=info")
            return False
            
    except Exception as e:
        print_error(f"Failed to send task: {str(e)}")
        return False


def test_result_storage():
    """Test result storage in MongoDB"""
    print_step(4, "Testing Result Storage in MongoDB")
    
    try:
        client = MongoClient('mongodb://localhost:27017/')
        db = client['legal_policy_analyzer']
        
        # Check if celery_taskmeta collection exists
        if 'celery_taskmeta' not in db.list_collection_names():
            print_error("celery_taskmeta collection not found")
            print_info("Run a task first to create the collection")
            return False
        
        # Get task results
        collection = db['celery_taskmeta']
        count = collection.count_documents({})
        
        print_success(f"Found {count} task result(s) in MongoDB")
        
        if count > 0:
            # Show recent tasks
            recent_tasks = list(collection.find().sort('_id', -1).limit(3))
            
            print_info("Recent tasks:")
            for task in recent_tasks:
                status = task.get('status', 'UNKNOWN')
                task_id = task.get('_id', 'unknown')
                result = task.get('result')
                
                print(f"  • Task {task_id[:8]}... - Status: {status} - Result: {result}")
        
        return True
        
    except Exception as e:
        print_error(f"Failed to check result storage: {str(e)}")
        return False


def test_queue_status():
    """Test RabbitMQ queue status"""
    print_step(5, "Testing RabbitMQ Queue Status")
    
    try:
        import subprocess
        
        # Run rabbitmqctl command
        result = subprocess.run(
            ['sudo', 'rabbitmqctl', 'list_queues', 'name', 'messages'],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if result.returncode == 0:
            print_success("Queue status retrieved")
            print(result.stdout)
            return True
        else:
            print_error("Failed to get queue status")
            print_info("Try manually: sudo rabbitmqctl list_queues")
            return False
            
    except subprocess.TimeoutExpired:
        print_error("Command timed out")
        return False
    except FileNotFoundError:
        print_info("rabbitmqctl not found (might need sudo)")
        print_info("Check management UI instead: http://localhost:15672")
        return True  # Not critical
    except Exception as e:
        print_error(f"Failed to check queue status: {str(e)}")
        return False


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("RabbitMQ + MongoDB Celery Setup Test")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = []
    
    # Run tests
    results.append(("RabbitMQ Connection", test_rabbitmq_connection()))
    results.append(("MongoDB Connection", test_mongodb_connection()))
    results.append(("Celery Task Execution", test_celery_task()))
    results.append(("Result Storage", test_result_storage()))
    results.append(("Queue Status", test_queue_status()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<40} {status}")
    
    print("="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60)
    
    if passed == total:
        print("\n🎉 All tests passed! Your setup is working correctly.")
        print("\nNext steps:")
        print("  1. Stop test worker if running")
        print("  2. Start your application worker:")
        print("     celery -A app.celery_worker worker --loglevel=info")
        print("  3. Start your FastAPI application:")
        print("     uvicorn app.main:app --reload")
        print("  4. Access RabbitMQ Management UI:")
        print("     http://localhost:15672 (guest/guest)")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
        print("\nCommon fixes:")
        print("  • RabbitMQ not running: sudo systemctl start rabbitmq-server")
        print("  • MongoDB not running: sudo systemctl start mongod")
        print("  • Worker not running: celery -A test_rabbitmq_setup worker &")
        return 1


if __name__ == '__main__':
    sys.exit(main())