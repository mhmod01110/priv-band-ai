import pika

# CONFIGURATION
RABBIT_HOST = 'localhost'
QUEUE_NAME = 'celery'  # Standard default queue name

def purge_queue():
    print(f"[*] Connecting to {RABBIT_HOST}...")
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(RABBIT_HOST))
        channel = connection.channel()
        
        # Purge returns the number of messages deleted
        method_frame = channel.queue_purge(queue=QUEUE_NAME)
        deleted_count = method_frame.method.message_count
        
        print(f"[SUCCESS] Purged {deleted_count} tasks from queue '{QUEUE_NAME}'.")
        connection.close()
        
    except pika.exceptions.ChannelClosedByBroker:
        print(f"[ERROR] Queue '{QUEUE_NAME}' does not exist.")
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == '__main__':
    purge_queue()