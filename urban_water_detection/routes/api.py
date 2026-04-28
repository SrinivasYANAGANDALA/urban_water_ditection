from flask import Blueprint, current_app, jsonify, request

from ..services.water_analysis import analyze_dataset, prepare_dataframe_from_bytes, prepare_dataframe_from_csv

api_bp = Blueprint("api", __name__)


@api_bp.post("/analyze")
def analyze_data():
    if "file" not in request.files:
        return jsonify({"error": "No CSV file uploaded."}), 400

    file = request.files["file"]
    if not file or not file.filename.lower().endswith(".csv"):
        return jsonify({"error": "Please upload a valid CSV file."}), 400

    try:
        threshold = float(request.form.get("threshold", "50"))
        if threshold < 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Threshold must be a non-negative number."}), 400

    try:
        df = prepare_dataframe_from_bytes(file.read())
        payload = analyze_dataset(df, threshold)
        return jsonify(payload)
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": str(exc)}), 400


@api_bp.get("/analyze-sample")
def analyze_sample_data():
    try:
        threshold = float(request.args.get("threshold", "50"))
        if threshold < 0:
            raise ValueError
    except ValueError:
        return jsonify({"error": "Threshold must be a non-negative number."}), 400

    sample_path = current_app.config["SAMPLE_DATA_FILE"]
    try:
        df = prepare_dataframe_from_csv(sample_path)
        payload = analyze_dataset(df, threshold)
        payload["sample_file"] = str(sample_path.name)
        return jsonify(payload)
    except Exception as exc:  # pragma: no cover
        return jsonify({"error": str(exc)}), 400
