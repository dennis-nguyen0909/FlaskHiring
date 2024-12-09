from flask import Flask, jsonify, request
from bson import ObjectId
from pymongo import MongoClient
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from flask_cors import CORS
import traceback
app = Flask(__name__)
# app.config['CORS_HEADERS'] = 'Content-Type'
# Kích hoạt CORS cho tất cả các đường dẫn và cho phép tất cả các nguồn (origin)
CORS(app,origins=["http://localhost:5173"], supports_credentials=True)
# CORS(app, supports_credentials=True)

# Kết nối MongoDB
client = MongoClient("mongodb://root:123456@localhost:27017/dennis?authSource=admin")
db = client['dennis']
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

        # Lấy kỹ năng của ứng viên
        candidate_skills_ids = candidate.get('skills', [])
        skills_al = list(
            skills_collection.find({"_id": {"$in": [ObjectId(skill_id) for skill_id in candidate_skills_ids]}}))
        candidate_skills = [skill['name'] for skill in skills_al]

        candidate_city = candidate.get("city_id");
        # Lấy kỹ năng yêu cầu của công việc
        job_skills = []
        for job in jobs:
            job_skill_ids = job.get('skills', [])
            job_skills_data = list(
                skills_employers_collection.find({"_id": {"$in": [ObjectId(skill_id) for skill_id in job_skill_ids]}}))
            job_skills.append([skill['name'] for skill in job_skills_data])

        # Chuyển đổi kỹ năng của ứng viên và công việc thành ma trận nhị phân
        mlb = MultiLabelBinarizer()

        # Ma trận kỹ năng công việc
        job_skills_matrix = mlb.fit_transform(job_skills)

        # Chuyển kỹ năng của ứng viên thành ma trận nhị phân
        candidate_skills_matrix = mlb.transform([candidate_skills])

        # Tính toán độ tương đồng cosine giữa kỹ năng ứng viên và kỹ năng công việc
        similarity_scores = cosine_similarity(candidate_skills_matrix, job_skills_matrix)[0]

        # Sắp xếp công việc theo mức độ phù hợp (độ tương đồng)
        sorted_job_indices = np.argsort(similarity_scores)[::-1]  # Sắp xếp từ cao xuống thấp

        # Pagination logic
        total_jobs = len(sorted_job_indices)  # Tổng số công việc
        start_idx = (current - 1) * page_size
        end_idx = start_idx + page_size
        paginated_indices = sorted_job_indices[start_idx:end_idx]  # Lấy công việc cho trang hiện tại

        # Tạo danh sách các công việc phù hợp
        job_suggestions = []
        for idx in paginated_indices:
            job = jobs[idx]

            # Lấy job_type_id từ job và tìm chi tiết job_type trong job_types_collection
            job_type_id = job.get('job_type')
            job_type_detail = job_types_collection.find_one({"_id": ObjectId(job_type_id)})
            employer_id= job.get('user_id')
            employer_detail = employers_collection.find_one({"_id": ObjectId(employer_id)},{
                "password":0,
                "progress_setup":0,

            })
            city_id= job.get('city_id')
            district_id= job.get('district_id')
            ward_id= job.get('ward_id')
            type_money=job.get('type_money')
            type_money_detail = currency_collection.find_one({"_id": ObjectId(type_money)},{})

            city_detail = city_collection.find_one({"_id": ObjectId(city_id)},{
                "districts":0
            })

            district_detail = district_collection.find_one({"_id": ObjectId(district_id)},{
                "wards":0
            })
            ward_detail = ward_collection.find_one({"_id": ObjectId(ward_id)},{})
            # Nếu tìm thấy job_type, thêm chi tiết vào thông tin công việc
            if job_type_detail:
                job["job_type"] = job_type_detail
                job["user_id"]=employer_detail
            if city_detail:
                job["city_id"] = city_detail
            if district_detail:
                job["district_id"] = district_detail
            if ward_detail:
                job["ward_id"] = ward_detail
            if type_money_detail:
                job["type_money"] = type_money_detail

            job_info = serialize_object(job)  # Serialize full job details
            similarity = similarity_scores[idx]
            job_info["similarity"] = similarity  # Add similarity score to job info
            if similarity > 0:
                job_info["similarity"] = similarity  # Add similarity score to job info
                job_suggestions.append(job_info)

        # Tính tổng số trang
        total_pages = int(np.ceil(len(job_suggestions) / page_size))
        # Định dạng phản hồi
        data = {
            "items": job_suggestions,  # Danh sách các công việc
            "meta": {
                "count": len(job_suggestions),  # Số công việc trên trang hiện tại
                "current_page": current,  # Trang hiện tại
                "per_page": page_size,  # Số lượng công việc mỗi trang
                "total":  len(job_suggestions),  # Tổng số công việc phù hợp
                "total_pages": total_pages  # Tổng số trang
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
        jobs = list(jobs_collection.find({"city_id": candidate_city_id}))  # Chỉ lấy các công việc cùng city_id

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

if __name__ == '__main__':
    app.run(debug=True)
