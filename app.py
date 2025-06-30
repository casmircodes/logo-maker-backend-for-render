from flask import Flask, request, jsonify, send_from_directory
import os, uuid, requests, base64, traceback

app = Flask(__name__, static_folder='generated_images', static_url_path='/generated_images')
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
MODEL_NAME = "gemini-2.0-flash-exp-image-generation"
API_ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"
OUTPUT_FOLDER = "generated_images"

if not os.path.exists(OUTPUT_FOLDER):
    os.makedirs(OUTPUT_FOLDER)

def generate_image_with_gemini(prompt, num_images=4):
    filenames = []
    for _ in range(num_images):
        try:
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseModalities": ["Text", "Image"]
                }
            }
            params = {"key": GOOGLE_API_KEY}
            response = requests.post(API_ENDPOINT, json=payload, params=params)
            response.raise_for_status()
            response_json = response.json()

            if "candidates" in response_json and response_json["candidates"]:
                parts = response_json["candidates"][0]["content"]["parts"]
                for part in parts:
                    if "inlineData" in part and "data" in part["inlineData"]:
                        image_data = part["inlineData"]["data"]
                        filename = f"image_{uuid.uuid4().hex}.png"
                        filepath = os.path.join(OUTPUT_FOLDER, filename)
                        with open(filepath, "wb") as f:
                            f.write(base64.b64decode(image_data))
                        filenames.append(filename)
                        break
        except Exception as e:
            print(f"Error: {traceback.format_exc()}")
    return filenames

@app.route("/generate-logos", methods=["POST"])
def generate_logos_api():
    data = request.get_json()
    business_name = data.get("businessname", "")
    slogan = data.get("slogan", "")
    industry = data.get("industry", "")

    if not business_name or not industry:
        return jsonify({"error": "Business name and industry are required."}), 400

    prompt = f"I need a colorful traditional logo for my {industry} brand named {business_name}. Use matured and professional colors. Also make sure it is tempting and attractive to the eyes. Play with the brand name and the icon. White background. In {industry} industry logo style. Leverage 60, 30, 10 color principle. Make sure the concept of the logo icon is clear and meaningful. Remember on a white background."

    if slogan:
        prompt += f" My business slogan is {slogan}"

    filenames = generate_image_with_gemini(prompt)

    if not filenames:
        return jsonify({"error": "Failed to generate logos"}), 500

    image_urls = [f"/generated_images/{filename}" for filename in filenames]
    return jsonify({"images": image_urls})

@app.route("/generated_images/<filename>")
def serve_image(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

if __name__ == "__main__":
    app.run(debug=True)
