from flask import Flask, jsonify, request
from bson import ObjectId
from pymongo import MongoClient
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.feature_extraction.text import TfidfVectorizer
from services.pdf_service import extract_text_from_pdf
from services.gemini_service import analyze_cv
from services.api import post_to_api,updateUser
import numpy as np
from flask_cors import CORS
import traceback
from dotenv import load_dotenv
import os
# Load environment variables from .env file
load_dotenv()
# Lấy các thông tin từ biến môi trường
MONGO_URL =os.getenv("MONGO_URL")
MONGO_DB =os.getenv("MONGO_DB")
# Kết nối MongoDB bằng thông tin từ biến môi trường
client = MongoClient(MONGO_URL)
print("client",client)
app = Flask(__name__)
# app.config['CORS_HEADERS'] = 'Content-Type'
# Kích hoạt CORS cho tất cả các đường dẫn và cho phép tất cả các nguồn (origin)
CORS(app,origins=["http://localhost:5173","https://frontend-hiring-minhduys-projects.vercel.app","https://hire-dev.online"], supports_credentials=True)
# CORS(app, supports_credentials=True)
# check cicd
# Kết nối MongoDB
db = client[MONGO_DB]
jobs_collection = db['jobs']
candidates_collection = db['users']
employers_collection = db['users']
skills_collection = db['skills']
skills_employers_collection = db['skillemployers']
job_types_collection = db['jobtypes']
city_collection = db['cities']
district_collection = db['districts']
ward_collection = db['wards']
currency_collection = db['currencies']
# Hàm để chuyển ObjectId thành chuỗi cho tất cả các ObjectId trong document
def serialize_object(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, dict):
        return {k: serialize_object(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_object(item) for item in obj]
    return obj

@app.route('/suggests/<candidate_id>', methods=['GET','OPTIONS'])
def predict_all_jobs_for_candidate(candidate_id):
    try:
        # Lấy thông tin trang hiện tại và kích thước trang từ query parameters
        current = int(request.args.get('current', 1))  # Default to page 1
        page_size = int(request.args.get('pageSize', 10))  # Default to 10 items per page

        # Lấy thông tin ứng viên từ MongoDB
        candidate = candidates_collection.find_one({"_id": ObjectId(candidate_id)})
        if not candidate:
            return jsonify({"error": f"Không tìm thấy ứng viên {candidate_id}."}), 404
        
        # Lấy dữ liệu công việc từ MongoDB
        jobs = list(jobs_collection.find())  # Lấy tất cả công việc
        jobs = list(jobs_collection.find({}, {
            "title": 1,
            "job_type":1,
            "district_id":1,
            "city_id":1,
            "type_money":1,
            "user_id":1,
            "ward_id":1,
            "salary_range":1,
            "is_negotiable":1,
            "skills":1
            }))  # Lấy tất cả công việc, chỉ lấy trường "title"

        # Lấy kỹ năng của ứng viên
        candidate_skills_ids = candidate.get('skills', [])
        skills_al = list(
                skills_collection.find({"_id": {"$in": [ObjectId(skill_id) for skill_id in candidate_skills_ids]}}, {"name": 1}))
        candidate_skills = [skill['name'] for skill in skills_al]
        candidate_skills = [skill.strip().lower() for skill in candidate_skills]

        # Ghép các kỹ năng thành một chuỗi duy nhất để so sánh với tiêu đề công việc
        candidate_skills_str = " ".join(candidate_skills)
        # Lấy kỹ năng yêu cầu của công việc
        job_skills = []
        job_titles = []
        for job in jobs:
            job_skill_ids = job.get('skills', [])
            job_skills_data = list(
                skills_employers_collection.find({"_id": {"$in": [ObjectId(skill_id) for skill_id in job_skill_ids]}}))
            job_skills.append([skill['name'] for skill in job_skills_data])
            job_titles.append(job.get('title', '').lower())  # Lấy tiêu đề công việc và chuyển về chữ thường

        # Chuẩn hóa kỹ năng công việc
        job_skills = [[skill.strip().lower() for skill in job_skill_list] for job_skill_list in job_skills]
        # Tính toán tương đồng giữa kỹ năng của ứng viên và kỹ năng công việc
        mlb = MultiLabelBinarizer()
        mlb.fit(job_skills)
        mlb.classes_ = np.unique(np.concatenate([mlb.classes_, candidate_skills]))

        job_skills_matrix = mlb.transform(job_skills)
        candidate_skills_matrix = mlb.transform([candidate_skills])

        similarity_scores_skills = cosine_similarity(candidate_skills_matrix, job_skills_matrix)[0]

        # Tính toán tương đồng giữa tiêu đề công việc và kỹ năng ứng viên
        tfidf_vectorizer = TfidfVectorizer(stop_words='english')
        tfidf_matrix = tfidf_vectorizer.fit_transform([candidate_skills_str] + job_titles)
        similarity_scores_titles = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:])[0]

        # Kết hợp điểm số tương đồng giữa kỹ năng và tiêu đề công việc
        combined_similarity_scores = (similarity_scores_skills + similarity_scores_titles) / 2

        # Sắp xếp công việc theo mức độ phù hợp (độ tương đồng)
        sorted_job_indices = np.argsort(combined_similarity_scores)[::-1]

        # Pagination logic
        total_jobs = len(sorted_job_indices)
        start_idx = (current - 1) * page_size
        end_idx = start_idx + page_size
        paginated_indices = sorted_job_indices[start_idx:end_idx]

        job_suggestions = []
        for idx in paginated_indices:
            job = jobs[idx]
            # Lấy chi tiết job type, city, district, ward và employer như trong đoạn mã gốc
            job_type_id = job.get('job_type')
            job_type_detail = job_types_collection.find_one({"_id": ObjectId(job_type_id)})
            employer_id = job.get('user_id')
            employer_detail = employers_collection.find_one({"_id": ObjectId(employer_id)}, {
                "avatar": 1,
                "avatar_company": 1,
                "city_id":1,
                "company_name":1,
                "ward_id":1
    
            })
            city_id = job.get('city_id')
            district_id = job.get('district_id')
            ward_id = job.get('ward_id')
            type_money = job.get('type_money')
            type_money_detail = currency_collection.find_one({"_id": ObjectId(type_money)}, {})

            city_detail = city_collection.find_one({"_id": ObjectId(city_id)}, {
                "districts": 0
            })

            district_detail = district_collection.find_one({"_id": ObjectId(district_id)}, {
                "wards": 0
            })
            ward_detail = ward_collection.find_one({"_id": ObjectId(ward_id)}, {})

            # Nếu tìm thấy job_type, thêm chi tiết vào thông tin công việc
            if job_type_detail:
                job["job_type"] = job_type_detail
                job["user_id"] = employer_detail
            if city_detail:
                job["city_id"] = city_detail
            if district_detail:
                job["district_id"] = district_detail
            if ward_detail:
                job["ward_id"] = ward_detail
            if type_money_detail:
                job["type_money"] = type_money_detail

            job_info = serialize_object(job)  # Serialize full job details
            similarity = combined_similarity_scores[idx]
            job_info["similarity"] = similarity  # Add similarity score to job info
            if similarity > 0:
                job_suggestions.append(job_info)

        # Tính tổng số trang
        total_pages = int(np.ceil(len(job_suggestions) / page_size))

        data = {
            "items": job_suggestions,
            "meta": {
                "count": len(job_suggestions),
                "current_page": current,
                "per_page": page_size,
                "total": len(job_suggestions),
                "total_pages": total_pages
            }
        }
        response_data = {
            "data": data,
            "message": "Success",
            "statusCode": 201
        }

        return jsonify(response_data)

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400


@app.route('/suggests_by_city/<candidate_id>', methods=['GET', 'OPTIONS'])
def suggest_jobs_by_city(candidate_id):
    try:
        # Lấy thông tin trang hiện tại và kích thước trang từ query parameters
        current = int(request.args.get('current', 1))  # Default to page 1
        page_size = int(request.args.get('pageSize', 10))  # Default to 10 items per page

        # Lấy thông tin ứng viên từ MongoDB
        candidate = candidates_collection.find_one({"_id": ObjectId(candidate_id)})
        if not candidate:
            return jsonify({"error": f"Không tìm thấy ứng viên {candidate_id}."}), 404

        # Lấy city_id của ứng viên
        candidate_city_id = candidate.get('city_id')

        # Lấy dữ liệu công việc từ MongoDB và lọc theo city_id
        jobs = list(jobs_collection.find({}, {"_id": 1, "skills": 1, "title": 1, "job_type": 1, "user_id": 1, "city_id": 1, "district_id": 1, "ward_id": 1, "type_money": 1,"salary_range":1,  "is_negotiable":1,
            "skills":1}))

        # Pagination logic
        total_jobs = len(jobs)  # Tổng số công việc
        start_idx = (current - 1) * page_size
        end_idx = start_idx + page_size
        paginated_jobs = jobs[start_idx:end_idx]  # Lấy công việc cho trang hiện tại

        # Tạo danh sách các công việc phù hợp
        job_suggestions = []
        for job in paginated_jobs:
            # Lấy job_type_id từ job và tìm chi tiết job_type trong job_types_collection
            job_type_id = job.get('job_type')
            job_type_detail = job_types_collection.find_one({"_id": ObjectId(job_type_id)})

            employer_id = job.get('user_id')
            employer_detail = employers_collection.find_one({"_id": ObjectId(employer_id)}, {
                "password": 0,
                "progress_setup": 0,
                "account_type":0
            })

            city_id = job.get('city_id')
            district_id = job.get('district_id')
            ward_id = job.get('ward_id')
            type_money = job.get('type_money')

            type_money_detail = currency_collection.find_one({"_id": ObjectId(type_money)}, {})
            city_detail = city_collection.find_one({"_id": ObjectId(city_id)}, {"districts": 0})
            district_detail = district_collection.find_one({"_id": ObjectId(district_id)}, {"wards": 0})
            ward_detail = ward_collection.find_one({"_id": ObjectId(ward_id)}, {})
            print("duydeptrai",job_type_id)
            print("duydeptrai",job_type_detail)
            # Gán chi tiết vào thông tin công việc
            if job_type_detail:
                job["job_type"] = job_type_detail
                job["user_id"] = employer_detail
            if city_detail:
                job["city_id"] = city_detail
            if district_detail:
                job["district_id"] = district_detail
            if ward_detail:
                job["ward_id"] = ward_detail
            if type_money_detail:
                job["type_money"] = type_money_detail

            job_info = serialize_object(job)  # Serialize full job details
            job_suggestions.append(job_info)

        # Tính tổng số trang
        total_pages = int(np.ceil(total_jobs / page_size))

        # Định dạng phản hồi
        data = {
            "items": job_suggestions,  # Danh sách các công việc
            "meta": {
                "count": len(job_suggestions),  # Số công việc trên trang hiện tại
                "current_page": current,  # Trang hiện tại
                "per_page": page_size,  # Số lượng công việc mỗi trang
                "total": total_jobs,  # Tổng số công việc
                "total_pages": total_pages  # Tổng số trang
            }
        }
        response_data = {
            "data": data,
            "message": "Success",
            "statusCode": 200
        }

        return jsonify(response_data)

    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 400


@app.route("/")
def helloWorld():
  return "Hello, cross-origin-world!"

UPLOAD_FOLDER = "./uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/analyze-cv", methods=["POST"])
def analyze():
    file = request.files.get("cv_file")
    user_id = request.form.get("user_id")
    auth_header = request.headers.get("Authorization")
    token = auth_header.split(" ")[1]
    if not file:
        return jsonify({"error": "Thiếu file CV"}), 400
    if not user_id:
        return jsonify({"error": "Thiếu user_id"}), 400
    pdf_path = os.path.join(UPLOAD_FOLDER, file.filename)
    file.save(pdf_path)

    try:
        text = extract_text_from_pdf(pdf_path)
        result = analyze_cv(text)  # bỏ user_id nếu không cần
        if result.get("educations"):
            post_to_api("educations", result["educations"],token,user_id)

        if result.get("projects"):
            post_to_api("projects", result["projects"],token,user_id)

        if result.get("skills"):
            post_to_api("skills", result["skills"],token,user_id)

        if result.get("certificates"):
            post_to_api("certificates", result["certificates"],token,user_id)

        if result.get("experiences"):
            post_to_api("work-experiences", result["experiences"],token,user_id)

        if result.get("courses"):
            post_to_api("courses", result["courses"],token,user_id)

        if result.get("prizes"):
            post_to_api("prizes", result["prizes"],token,user_id)
        user_info = {}

        if result.get("total_experience_months") is not None:
            user_info["total_experience_months"] = result["total_experience_months"]

        if result.get("total_experience_years") is not None:
            user_info["total_experience_years"] = result["total_experience_years"]

        if result.get("no_experience") is not None:
            user_info["no_experience"] = result["no_experience"]

        if result.get("summary"):
            user_info["description"] = result["summary"]

        if result.get("role"):
            user_info["role_name"] = result["role"]

        if user_info:
            updateUser("users", user_info, token, user_id)
        return jsonify({"message": "Success", "statusCode": 201,"data":[]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# test
if __name__ == '__main__':
     app.run(host='0.0.0.0', port=5001, debug=True) 
