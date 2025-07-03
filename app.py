from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import uuid
import base64
import traceback
from queue import Queue
from threading import Thread
import time # For potential future use or debugging, not strictly necessary for this implementation

app = Flask(__name__)
CORS(app)  # Allow requests from frontend (Netlify)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

OUTPUT_FOLDER = "generated_images"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# --- Queue and Result Storage ---
request_queue = Queue()
# This dictionary will store the results of processed requests, keyed by request_id.
# It will hold {"status": "pending"}, {"status": "completed", "images": [...]}, or {"status": "failed", "error": "..."}
results_store = {}

def generate_images(prompt, num_images=4):
    """
    Generates a specified number of images based on a given prompt using the Google API.
    Saves the images locally and returns their relative URLs.
    """
    image_urls = []

    for _ in range(num_images):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseModalities": ["Text", "Image"]
                }
            }

            response = requests.post(API_ENDPOINT, json=payload, params={"key": GOOGLE_API_KEY})
            response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
            data = response.json()

            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    image_data = part["inlineData"]["data"]
                    filename = f"image_{uuid.uuid4().hex}.png"
                    filepath = os.path.join(OUTPUT_FOLDER, filename)
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(image_data))

                    image_url = f"/generated_images/{filename}"
                    image_urls.append(image_url)
                    break # Assuming only one image per part for simplicity
        except Exception as e:
            print(f"Image generation error: {e}\n{traceback.format_exc()}")
            # Continue to try generating other images even if one fails
            continue

    return image_urls

def worker():
    """
    Worker function that runs in a separate thread.
    It continuously pulls requests from the queue, processes them, and stores the results.
    """
    while True:
        # Get a request from the queue; block until an item is available
        request_id, prompt_data = request_queue.get()
        print(f"Worker: Processing request_id: {request_id}")

        try:
            # Construct the prompt from the dequeued data
            business_name = prompt_data["businessname"]
            slogan = prompt_data.get("slogan", "")
            industry = prompt_data["industry"]

            prompt = f"I need a colorful traditional logo for my {industry} brand named {business_name}. Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. Play with the brand name and the icon. White background. In {industry} industry logo style. Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. Remember on a white background."
            if slogan.strip():
                prompt += f" My business slogan is {slogan}"

            # Generate images
            image_urls = generate_images(prompt)

            # Store the results
            if image_urls:
                results_store[request_id] = {"status": "completed", "images": image_urls}
            else:
                results_store[request_id] = {"status": "failed", "error": "No images were generated."}

        except Exception as e:
            # If any error occurs during processing, mark the request as failed
            print(f"Worker: Error processing request {request_id}: {e}\n{traceback.format_exc()}")
            results_store[request_id] = {"status": "failed", "error": str(e)}
        finally:
            # Mark the task as done, allowing the queue to know it's processed
            request_queue.task_done()
            print(f"Worker: Finished request_id: {request_id}")

# Start the worker thread when the application initializes
# daemon=True ensures the thread will exit when the main program exits
worker_thread = Thread(target=worker, daemon=True)
worker_thread.start()
print("Worker thread started.")

@app.route("/generate-logo", methods=["POST"])
def generate_logo():
    """
    Endpoint to receive logo generation requests.
    It adds the request to a queue and immediately returns a request_id.
    """
    try:
        data = request.get_json()
        business_name = data.get("businessname")
        slogan = data.get("slogan", "")
        industry = data.get("industry")

        if not business_name or not industry:
            return jsonify({"error": "Business name and Industry are required."}), 400

        # Generate a unique ID for this request
        request_id = str(uuid.uuid4())

        # Add the request data to the queue
        request_queue.put((request_id, data))

        # Initialize the status for this request in the results store
        results_store[request_id] = {"status": "pending"}

        # Return the request ID to the client immediately
        return jsonify({"request_id": request_id, "status": "queued"}), 202 # 202 Accepted

    except Exception as e:
        print(f"Error in /generate-logo endpoint: {e}\n{traceback.format_exc()}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@app.route("/get-logo-status/<request_id>", methods=["GET"])
def get_logo_status(request_id):
    """
    Endpoint for clients to poll and check the status of their logo generation request.
    Returns the status and, if completed, the URLs of the generated images.
    """
    result = results_store.get(request_id)

    if result:
        if result["status"] == "completed":
            # Convert relative image URLs to full URLs before sending to the client
            full_urls = [request.host_url.rstrip("/") + url for url in result["images"]]
            return jsonify({"status": "completed", "images": full_urls})
        elif result["status"] == "failed":
            return jsonify({"status": "failed", "error": result["error"]}), 500
        else:  # "pending"
            return jsonify({"status": "pending"}), 200
    else:
        # If the request_id is not found, it might be an invalid ID or not yet added to store
        return jsonify({"error": "Request ID not found."}), 404

@app.route("/generated_images/<filename>")
def serve_image(filename):
    """
    Endpoint to serve the static generated image files.
    """
    return send_from_directory(OUTPUT_FOLDER, filename)

if __name__ == "__main__":
    # In a production environment, you might use a WSGI server like Gunicorn
    # For development, debug=True is fine.
    app.run(debug=True, threaded=True) # threaded=True is default for Flask's dev server, but good to be explicit







'''

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import requests
import uuid
import base64
import traceback

app = Flask(__name__)
CORS(app)  # Allow requests from frontend (Netlify)

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY environment variable not set.")

MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

OUTPUT_FOLDER = "generated_images"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


def generate_images(prompt, num_images=4):
    image_urls = []

    for _ in range(num_images):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseModalities": ["Text", "Image"]
                }
            }

            response = requests.post(API_ENDPOINT, json=payload, params={"key": GOOGLE_API_KEY})
            response.raise_for_status()
            data = response.json()

            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            for part in parts:
                if "inlineData" in part:
                    image_data = part["inlineData"]["data"]
                    filename = f"image_{uuid.uuid4().hex}.png"
                    filepath = os.path.join(OUTPUT_FOLDER, filename)
                    with open(filepath, "wb") as f:
                        f.write(base64.b64decode(image_data))

                    image_url = f"/generated_images/{filename}"
                    image_urls.append(image_url)
                    break
        except Exception as e:
            print(f"Image generation error: {e}\n{traceback.format_exc()}")
            continue

    return image_urls


@app.route("/generate-logo", methods=["POST"])
def generate_logo():
    try:
        data = request.get_json()
        business_name = data.get("businessname")
        slogan = data.get("slogan", "")
        industry = data.get("industry")

        if not business_name or not industry:
            return jsonify({"error": "Business name and Industry are required."}), 400

        # Dynamic prompt creation
        prompt = f"I need a colorful traditional logo for my {industry} brand named {business_name}. Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. Play with the brand name and the icon. White background. In {industry} industry logo style. Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. Remember on a white background."

        if slogan.strip():
            prompt += f" My business slogan is {slogan}"

        image_urls = generate_images(prompt)

        if not image_urls:
            return jsonify({"error": "Failed to generate images."}), 500

        full_urls = [request.host_url.rstrip("/") + url for url in image_urls]
        return jsonify({"images": full_urls})

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/generated_images/<filename>")
def serve_image(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)


if __name__ == "__main__":
    app.run(debug=True)

'''
