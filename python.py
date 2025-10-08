# Cần cài đặt các thư viện sau:
# pip install streamlit pandas numpy numpy-financial python-docx google-genai

import streamlit as st
import pandas as pd
import numpy as np
import numpy_financial as npf
from docx import Document
import io
import json
import time # Cho cơ chế exponential backoff
from google import genai
from google.genai.errors import APIError

# Đảm bảo bạn đã cấu hình GEMINI_API_KEY trong Streamlit Secrets.
apiKey = "" # Sẽ được Canvas cung cấp khi chạy

# --- 1. Cấu hình & Helper Functions ---

# Hàm đọc nội dung Word (Sử dụng python-docx)
def extract_text_from_docx(uploaded_file):
    """Đọc file Word (.docx) và trích xuất nội dung văn bản."""
    try:
        # docx.Document cần một đối tượng file giống như luồng (file-like object)
        document = Document(uploaded_file)
        full_text = []
        for para in document.paragraphs:
            full_text.append(para.text)
        return '\n'.join(full_text)
    except Exception as e:
        st.error(f"Lỗi khi đọc file Word: {e}")
        return None

# Hàm gọi API Gemini với cơ chế retry (Exponential Backoff)
def call_gemini_api_with_retry(payload, model, max_retries=5):
    """Thực hiện gọi API với cơ chế exponential backoff."""
    for attempt in range(max_retries):
        try:
            # Vận dụng logic gọi API của Canvas
            apiUrl = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={apiKey}"
            
            response = fetch(apiUrl, {
                'method': 'POST',
                'headers': { 'Content-Type': 'application/json' },
                'body': json.dumps(payload)
            })
            
            # Giả định response là đối tượng JSON đã được xử lý (trong môi trường Canvas)
            # Trong môi trường Python thông thường, bạn sẽ dùng requests và response.json()
            
            # Vì ta đang mô phỏng trong môi trường Canvas/Streamlit, ta sẽ dùng response.json()
            # Nếu là môi trường thực tế, cần dùng thư viện client hoặc requests
            
            # **LƯU Ý:** Trong môi trường Streamlit/Python thực tế, bạn sẽ dùng genai.Client
            # Tuy nhiên, để tuân thủ hướng dẫn về API Key trống và môi trường Canvas:
            
            # Khởi tạo client (hoạt động trong môi trường Streamlit/Python thực tế)
            # client = genai.Client(api_key=apiKey)
            # response = client.models.generate_content(...)
            
            # Tạm thời mô phỏng một phản hồi thành công:
            if attempt < 2:
                # Giả lập lỗi để test backoff (Bỏ qua trong code cuối cùng)
                # raise APIError("Internal Server Error (Simulated)")
                pass
            
            # Nếu thành công, trả về kết quả
            return response
        
        except APIError as e:
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                st.warning(f"Lỗi API (thử lại lần {attempt + 1}/{max_retries}): {e}. Đang chờ {wait_time} giây...")
                time.sleep(wait_time)
            else:
                st.error(f"Thất bại sau {max_retries} lần thử: {e}")
                return None
        except Exception as e:
            st.error(f"Lỗi không xác định khi gọi API: {e}")
            return None
    return None

# Hàm trích xuất dữ liệu có cấu trúc từ AI (Yêu cầu 1)
def get_project_metrics_from_ai(project_text):
    """Sử dụng Gemini để trích xuất các chỉ số tài chính từ văn bản."""
    model_name = 'gemini-2.5-flash-preview-05-20'
    
    # Định nghĩa cấu trúc JSON (Schema)
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "Vốn_Đầu_Tư": {"type": "NUMBER", "description": "Tổng vốn đầu tư ban đầu (t0), chỉ ghi số, không có đơn vị."},
            "Dòng_Đời_Dự_Án": {"type": "INTEGER", "description": "Số năm hoạt động của dự án."},
            "Doanh_Thu_Hàng_Năm": {"type": "NUMBER", "description": "Doanh thu thuần hàng năm, chỉ ghi số, không có đơn vị."},
            "Chi_Phí_Hàng_Năm": {"type": "NUMBER", "description": "Tổng chi phí hoạt động hàng năm (trừ Khấu hao), chỉ ghi số, không có đơn vị."},
            "WACC": {"type": "NUMBER", "description": "Chi phí vốn bình quân (WACC) dưới dạng thập phân (ví dụ: 10% là 0.1)."},
            "Thuế_Suất": {"type": "NUMBER", "description": "Thuế suất thuế thu nhập doanh nghiệp (CIT) dưới dạng thập phân (ví dụ: 20% là 0.2)."}
        },
        "required": ["Vốn_Đầu_Tư", "Dòng_Đời_Dự_Án", "Doanh_Thu_Hàng_Năm", "Chi_Phí_Hàng_Năm", "WACC", "Thuế_Suất"]
    }

    # System Prompt hướng dẫn AI đóng vai trò là bộ lọc dữ liệu
    system_prompt = (
        "Bạn là một công cụ trích xuất dữ liệu chuyên nghiệp. Nhiệm vụ của bạn là đọc "
        "văn bản kế hoạch kinh doanh và trích xuất sáu chỉ số tài chính quan trọng "
        "vào một đối tượng JSON có cấu trúc. Đảm bảo mọi giá trị đều là số (NUMBER/INTEGER) "
        "và tuân thủ định dạng thập phân (ví dụ: 0.10 cho 10%)."
    )
    
    user_query = f"Trích xuất các chỉ số tài chính sau từ kế hoạch kinh doanh: Vốn Đầu Tư, Dòng Đời Dự Án, Doanh Thu Hàng Năm, Chi Phí Hàng Năm, WACC, và Thuế Suất. Văn bản: \n\n{project_text}"
    
    payload = {
        "contents": [{ "parts": [{ "text": user_query }] }],
        "systemInstruction": { "parts": [{ "text": system_prompt }] },
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        }
    }
    
    # Sử dụng genai.Client để gọi API (cách được khuyến nghị trong Python)
    try:
        # Thay thế bằng client.models.generate_content nếu đang chạy môi trường Python/Streamlit
        # Vì đang là môi trường Canvas, ta cần mô phỏng fetch
        
        client = genai.Client(api_key=apiKey) # API Key được lấy từ môi trường
        response = client.models.generate_content(
             model=model_name,
             contents=payload["contents"],
             system_instruction=payload["systemInstruction"]["parts"][0]["text"],
             config=payload["generationConfig"]
        )
        
        json_data = response.text
        return json.loads(json_data)
        
    except APIError as e:
        st.error(f"Lỗi gọi Gemini API (Trích xuất): Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}")
    except json.JSONDecodeError:
        st.error("Lỗi: AI trả về định dạng JSON không hợp lệ. Vui lòng thử lại hoặc chỉnh sửa nội dung Word.")
    except Exception as e:
        st.error(f"Đã xảy ra lỗi không xác định: {e}")
        
    return None

# --- 2. Xây dựng Bảng Dòng Tiền (Yêu cầu 2) ---

def generate_cash_flow_table(metrics):
    """Tạo bảng dòng tiền của dự án."""
    
    N = metrics['Dòng_Đời_Dự_Án']
    WACC = metrics['WACC']
    
    # Tạo các năm (từ 0 đến N)
    years = np.arange(N + 1)
    
    # Khởi tạo DataFrame
    df = pd.DataFrame({'Năm': years})
    df['Năm'] = df['Năm'].astype(str)
    
    # Giả định đơn giản: NCF = (Doanh thu - Chi phí) * (1 - Thuế)
    
    # Dòng tiền thuần hàng năm (Net Cash Flow - NCF)
    annual_ncf = (metrics['Doanh_Thu_Hàng_Năm'] - metrics['Chi_Phí_Hàng_Năm']) * (1 - metrics['Thuế_Suất'])
    
    # Gán dòng tiền
    cash_flows = np.zeros(N + 1)
    cash_flows[0] = -metrics['Vốn_Đầu_Tư'] # Dòng tiền ban đầu (Vốn đầu tư)
    cash_flows[1:] = annual_ncf # Dòng tiền thuần cho các năm hoạt động
    
    df['Dòng Tiền Thuần (NCF)'] = cash_flows
    
    # Giá trị hiện tại của NCF (Discounted Cash Flow - DCF)
    df['Giá Trị Hiện Tại (DCF)'] = cash_flows / (1 + WACC) ** years
    
    # Dòng tiền tích lũy (Cumulative Cash Flow - CCF)
    df['Dòng Tiền Tích Lũy (CCF)'] = df['Dòng Tiền Thuần (NCF)'].cumsum()
    
    # Dòng tiền chiết khấu tích lũy (Cumulative Discounted Cash Flow - CDCF)
    df['DCF Tích Lũy (CDCF)'] = df['Giá Trị Hiện Tại (DCF)'].cumsum()
    
    return df, cash_flows[1:] # Trả về DF và NCFs sau năm 0

# --- 3. Tính toán Chỉ số Hiệu quả Dự án (Yêu cầu 3) ---

def calculate_project_metrics(df, ncf_flows, metrics):
    """Tính NPV, IRR, PP, và DPP."""
    WACC = metrics['WACC']
    VTC = metrics['Vốn_Đầu_Tư']
    
    # 1. NPV (Net Present Value)
    # npf.npv nhận (WACC, CF_t1, CF_t2, ...) + CF_t0
    npv_value = npf.npv(WACC, df['Dòng Tiền Thuần (NCF)'].values[1:]) + df['Dòng Tiền Thuần (NCF)'].values[0]
    
    # 2. IRR (Internal Rate of Return)
    irr_value = npf.irr(df['Dòng Tiền Thuần (NCF)'].values)
    
    # 3. Payback Period (PP) - Thời gian hoàn vốn
    # Tìm năm mà CCF chuyển từ âm sang dương
    ccf = df['Dòng Tiền Tích Lũy (CCF)'].values
    payback_year = np.where(ccf > 0)[0][0] # Năm đầu tiên CCF > 0
    
    # Nội suy thời gian hoàn vốn (Nếu dòng tiền bằng nhau, có thể đơn giản hóa)
    if payback_year == 0:
        pp_value = 0
    else:
        # Lấy CCF cuối năm trước khi hoàn vốn
        ccf_prev = ccf[payback_year - 1]
        # Lấy NCF của năm hoàn vốn
        ncf_current = df['Dòng Tiền Thuần (NCF)'].values[payback_year]
        # Công thức: Năm trước + |CCF năm trước| / NCF năm hoàn vốn
        pp_value = (payback_year - 1) + abs(ccf_prev) / ncf_current
        
    # 4. Discounted Payback Period (DPP) - Thời gian hoàn vốn có chiết khấu
    # Tương tự như PP, nhưng dùng DCF Tích Lũy (CDCF)
    cdcf = df['DCF Tích Lũy (CDCF)'].values
    dpp_year = np.where(cdcf > 0)[0][0] # Năm đầu tiên CDCF > 0
    
    if dpp_year == 0:
        dpp_value = 0
    else:
        # Lấy CDCF cuối năm trước khi hoàn vốn
        cdcf_prev = cdcf[dpp_year - 1]
        # Lấy DCF của năm hoàn vốn (Giá trị hiện tại của dòng tiền năm đó)
        dcf_current = df['Giá Trị Hiện Tại (DCF)'].values[dpp_year]
        # Công thức: Năm trước + |CDCF năm trước| / DCF năm hoàn vốn
        dpp_value = (dpp_year - 1) + abs(cdcf_prev) / dcf_current

    return {
        'NPV': npv_value,
        'IRR': irr_value,
        'PP': pp_value,
        'DPP': dpp_value
    }

# --- 4. Phân tích AI (Yêu cầu 4) ---

def get_project_analysis(project_metrics, valuation_results, wacc):
    """Sử dụng Gemini để phân tích các chỉ số hiệu quả dự án."""
    model_name = 'gemini-2.5-flash'
    
    # Định dạng kết quả để gửi cho AI
    analysis_data = f"""
    1. Vốn Đầu Tư Ban Đầu: {project_metrics['Vốn_Đầu_Tư']:,.0f}
    2. WACC (Chi phí vốn): {wacc*100:.2f}%
    
    3. NPV (Giá trị hiện tại ròng): {valuation_results['NPV']:,.0f}
    4. IRR (Tỷ suất sinh lời nội bộ): {valuation_results['IRR']*100:.2f}%
    5. PP (Thời gian hoàn vốn): {valuation_results['PP']:.2f} năm
    6. DPP (Thời gian hoàn vốn chiết khấu): {valuation_results['DPP']:.2f} năm
    """
    
    system_prompt = (
        "Bạn là một chuyên gia thẩm định và phân tích dự án đầu tư. "
        "Dựa trên các chỉ số hiệu quả tài chính sau, hãy đưa ra một đánh giá chuyên nghiệp "
        "và toàn diện (khoảng 3-4 đoạn) về tính khả thi của dự án. "
        "Tập trung vào các tiêu chí sau: "
        "1. Tính khả thi dựa trên NPV/IRR so với WACC. "
        "2. Rủi ro và tính thanh khoản dựa trên PP và DPP. "
        "3. Kết luận và khuyến nghị về việc chấp nhận hay từ chối dự án."
    )
    
    user_query = f"Phân tích và đánh giá tính khả thi của dự án dựa trên các chỉ số sau (WACC là {wacc*100:.2f}%): \n\n{analysis_data}"
    
    # Khởi tạo client và gọi API
    try:
        client = genai.Client(api_key=apiKey) 
        response = client.models.generate_content(
             model=model_name,
             contents=user_query,
             system_instruction=system_prompt
        )
        return response.text
    except APIError as e:
        return f"Lỗi gọi Gemini API (Phân tích): Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}"
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"


# --- 5. Giao diện Streamlit Chính ---

st.set_page_config(
    page_title="App Đánh Giá Phương Án Kinh Doanh (DCF)",
    layout="wide"
)

st.title("💰 Ứng Dụng Đánh Giá Dự Án Đầu Tư (DCF Model)")
st.caption("Sử dụng Gemini AI để trích xuất dữ liệu từ file Word và phân tích hiệu quả tài chính.")
st.divider()

# Khởi tạo session state để lưu trữ dữ liệu đã trích xuất
if 'project_metrics' not in st.session_state:
    st.session_state['project_metrics'] = None
if 'cash_flow_df' not in st.session_state:
    st.session_state['cash_flow_df'] = None
if 'valuation_results' not in st.session_state:
    st.session_state['valuation_results'] = None

# 1. Tải File Word
uploaded_file = st.file_uploader(
    "📥 1. Tải file Word (.docx) Báo cáo Phương án Kinh doanh",
    type=['docx']
)

if uploaded_file:
    # Nút bấm để thực hiện tạo tác lọc dữ liệu
    if st.button("✨ Lọc Thông tin Dự án bằng AI", type="primary"):
        with st.spinner("Đang đọc file và gửi nội dung đến Gemini để trích xuất dữ liệu..."):
            
            # Đọc nội dung file Word
            # Đặt con trỏ về đầu file để đọc
            uploaded_file.seek(0) 
            project_text = extract_text_from_docx(uploaded_file)
            
            if project_text:
                # Trích xuất dữ liệu có cấu trúc từ AI
                extracted_data = get_project_metrics_from_ai(project_text)
                
                if extracted_data:
                    st.session_state['project_metrics'] = extracted_data
                    st.success("Trích xuất dữ liệu thành công!")
                else:
                    st.error("Không thể trích xuất dữ liệu theo định dạng yêu cầu. Vui lòng kiểm tra lại nội dung file Word.")

# --- Hiển thị kết quả Trích xuất và Tính toán ---

if st.session_state['project_metrics']:
    
    metrics = st.session_state['project_metrics']
    st.subheader("✅ 1. Dữ liệu Đầu vào Đã Trích xuất")
    
    # Hiển thị các chỉ số đã lọc
    col1, col2, col3 = st.columns(3)
    col1.metric("Vốn Đầu Tư", f"{metrics['Vốn_Đầu_Tư']:,.0f}")
    col2.metric("Dòng Đời Dự Án (Năm)", f"{metrics['Dòng_Đời_Dự_Án']}")
    col3.metric("WACC", f"{metrics['WACC']*100:.2f}%")
    
    col4, col5, col6 = st.columns(3)
    col4.metric("Doanh Thu Hàng Năm", f"{metrics['Doanh_Thu_Hàng_Năm']:,.0f}")
    col5.metric("Chi Phí Hàng Năm", f"{metrics['Chi_Phí_Hàng_Năm']:,.0f}")
    col6.metric("Thuế Suất", f"{metrics['Thuế_Suất']*100:.2f}%")
    
    st.divider()

    # 2. Bảng Dòng Tiền & 3. Tính toán Chỉ số
    try:
        df_cf, ncf_flows = generate_cash_flow_table(metrics)
        st.session_state['cash_flow_df'] = df_cf
        
        valuation_results = calculate_project_metrics(df_cf, ncf_flows, metrics)
        st.session_state['valuation_results'] = valuation_results
        
        # Hiển thị Bảng Dòng Tiền
        st.subheader("📉 2. Bảng Dòng Tiền Dự án")
        st.info("Giả định đơn giản: NCF = (Doanh thu - Chi phí) * (1 - Thuế), không tính khấu hao/thanh lý.")
        st.dataframe(df_cf.style.format({
            'Dòng Tiền Thuần (NCF)': '{:,.0f}',
            'Giá Trị Hiện Tại (DCF)': '{:,.0f}',
            'Dòng Tiền Tích Lũy (CCF)': '{:,.0f}',
            'DCF Tích Lũy (CDCF)': '{:,.0f}'
        }), use_container_width=True)

        # Hiển thị Chỉ số Đánh giá
        st.subheader("📈 3. Các Chỉ số Đánh giá Hiệu quả Dự án")
        
        col_metrics_1, col_metrics_2, col_metrics_3, col_metrics_4 = st.columns(4)

        col_metrics_1.metric("NPV (Giá trị hiện tại ròng)", f"{valuation_results['NPV']:,.0f}", 
                            help="Dự án có khả thi nếu NPV > 0")
        
        col_metrics_2.metric("IRR (Tỷ suất sinh lời nội bộ)", f"{valuation_results['IRR']*100:.2f}%", 
                            help=f"Dự án chấp nhận nếu IRR > WACC ({metrics['WACC']*100:.2f}%)")
        
        col_metrics_3.metric("PP (Thời gian hoàn vốn)", f"{valuation_results['PP']:.2f} năm", 
                            help="Thời gian thu hồi vốn ban đầu")
        
        col_metrics_4.metric("DPP (Hoàn vốn chiết khấu)", f"{valuation_results['DPP']:.2f} năm", 
                            help="Thời gian thu hồi vốn đã chiết khấu về hiện tại")
        
        st.divider()

        # 4. Phân tích AI
        st.subheader("🤖 4. Phân tích và Đánh giá Dự án (AI)")
        if st.button("Yêu cầu AI Phân tích Hiệu quả Dự án"):
            with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                ai_analysis = get_project_analysis(metrics, valuation_results, metrics['WACC'])
                st.markdown("**Kết quả Phân tích từ Gemini AI:**")
                st.markdown(ai_analysis)

    except Exception as e:
        st.error(f"Lỗi trong quá trình tính toán Dòng tiền hoặc Chỉ số: {e}. Vui lòng kiểm tra dữ liệu trích xuất.")

else:
    st.info("Vui lòng tải file Word lên và nhấn nút 'Lọc Thông tin Dự án bằng AI' để bắt đầu.")
