import os
import time
import base64
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(
    api_key=os.getenv("API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    timeout=60,
)

MODEL = "openrouter/free"

HOURLY_RATE = 25        # תשנה למחיר אמיתי באזור שלך
WASTE_REMOVAL_FEE = 40  # תשלום קבוע על פינוי פסולת
CALIBRATION = 0.5       # עבודה אמיתית אחת: ה-AI אמר 6 שעות, בפועל 3


def encode_image(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def analyze_garden(image_path):
    image_b64 = encode_image(image_path)

    for attempt in range(1, 4):
        response = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a garden repair expert. Look at the photo and reply "
                        "ONLY with JSON in this format: "
                        '{"problem": str, "size": "none|small|medium|large", '
                        '"work_needed": [str], "estimated_hours": number}. '
                        "Use these rules for estimated_hours: small job = 1-4 hours, "
                        "medium job = 4-10 hours, large job = 10-20 hours. "
                        "Only include work that is clearly needed in the photo. "
                        "Do not suggest building new beds or pathways unless the photo shows they are missing. "
                        "Assume one experienced professional working with power tools (brush cutter, mower, trimmer). "
                        "Estimate realistic working time, not the maximum possible. "
                        "If the grass is freshly cut, the area is clean and no repair is needed, "
                        "use size 'none', an empty work_needed list and estimated_hours 0. "
                        "Describe only what is visible; do not suggest watering or fertilizing "
                        "unless the plants clearly look dying."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "What is wrong with this garden?"},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                    ],
                },
            ],
        )

        if response.choices:
            text = response.choices[0].message.content or ""
            text = text.replace("```json", "").replace("```", "").strip()
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                print(f"Attempt {attempt}: answer was not valid JSON:\n{text}\n")
        else:
            print(f"Attempt {attempt}: empty response from the model.")
            print("Error:", getattr(response, "error", None) or response.model_extra)

        time.sleep(3)

    raise RuntimeError("The model failed 3 times. Try again later or change MODEL.")


def calculate_price(result):
    hours = result["estimated_hours"] * CALIBRATION
    if hours <= 0:
        return 0, 0

    base = hours * HOURLY_RATE

    work = " ".join(result["work_needed"]).lower()
    if "remove" in work or "waste" in work or "clear" in work:
        base += WASTE_REMOVAL_FEE

    low = round(base * 0.8)
    high = round(base * 1.2)
    return low, high


if __name__ == "__main__":
    folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "photos")
    files = [f for f in os.listdir(folder) if f.lower().endswith((".jpg", ".jpeg"))]

    print(f"Found {len(files)} photos\n")

    for name in files:
        print("=" * 40)
        print("Photo:", name)
        try:
            result = analyze_garden(os.path.join(folder, name))
            low, high = calculate_price(result)
            print("Problem:", result["problem"])
            print("Work:", ", ".join(result["work_needed"]) or "none")
            print("Size:", result["size"], "| AI hours:", result["estimated_hours"])
            if low == 0 and high == 0:
                print("Price: no work needed")
            else:
                print(f"Price: {low} to {high}")
        except Exception as e:
            print("Failed:", e)
        time.sleep(2)


