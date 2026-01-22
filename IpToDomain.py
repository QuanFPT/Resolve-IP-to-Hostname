import socket
import sys
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple, Optional

MAX_WORKERS = 50          # Số luồng đồng thời
TIMEOUT = 4.0             # giây

def is_valid_ip(ip: str) -> bool:
    ip = ip.strip()
    if not ip or ip.startswith('#'):
        return False
    try:
        socket.inet_pton(socket.AF_INET, ip)
        return True
    except:
        try:
            socket.inet_pton(socket.AF_INET6, ip)
            return True
        except:
            return False


def ip_to_hostname(ip: str) -> Tuple[str, str]:
    """Trả về (hostname_or_fallback, ip)"""
    ip = ip.strip()
    try:
        socket.setdefaulttimeout(TIMEOUT)
        result = socket.gethostbyaddr(ip)
        return result[0], ip
    except socket.herror:
        return ip, ip                # ← No PTR → dùng IP làm hostname
    except socket.gaierror:
        return ip, ip                # Invalid → dùng IP
    except socket.timeout:
        return ip, ip                # Timeout → dùng IP
    except Exception as e:
        return ip, ip                # Các lỗi khác → dùng IP


def process_ip_file(input_file: str, output_file: Optional[str] = None):
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Không tìm thấy file input: {input_file}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Lỗi đọc file input: {e}", file=sys.stderr)
        sys.exit(1)

    valid_ips = [ip for ip in lines if is_valid_ip(ip)]

    print(f"Tổng IP hợp lệ: {len(valid_ips)}", file=sys.stderr)
    if valid_ips:
        print(f"Đang tra cứu đa luồng ({MAX_WORKERS} workers, timeout {TIMEOUT}s)...", file=sys.stderr)

    results = []

    if valid_ips:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_ip = {executor.submit(ip_to_hostname, ip): ip for ip in valid_ips}

            for future in as_completed(future_to_ip):
                hostname_or_ip, ip = future.result()
                results.append((hostname_or_ip, ip))

    # Tạo map ip -> hostname (hoặc IP nếu không resolve được)
    ip_to_result = {ip: hostname for hostname, ip in results}

    # In ra console (giữ format hostname:ip, hiển thị lỗi nếu có)
    for line in lines:
        ip = line.strip()
        if not ip or ip.startswith('#'):
            continue
        if not is_valid_ip(ip):
            print(f"Invalid IP format:{ip}")
        else:
            resolved = ip_to_result.get(ip, ip)
            # In lỗi thật nếu muốn debug, nhưng theo yêu cầu cũ vẫn in resolved
            print(f"{resolved}:{ip}")

    # Lưu CSV: hostname luôn là resolved value (IP nếu không có PTR)
    if output_file:
        if not output_file.lower().endswith('.csv'):
            output_file += '.csv'
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['hostname', 'ip'])  # header
                
                for ip in valid_ips:
                    hostname = ip_to_result.get(ip, ip)
                    writer.writerow([hostname, ip])
            
            print(f"\nKết quả đã lưu vào file CSV: {output_file}", file=sys.stderr)
            print(f"- Cột hostname: tên miền nếu resolve được, ngược lại ghi chính IP đó", file=sys.stderr)
            print(f"- Chỉ lưu các IP hợp lệ", file=sys.stderr)
        except Exception as e:
            print(f"Lỗi lưu file CSV: {e}", file=sys.stderr)

    print(f"\nHoàn thành.", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Cách dùng: python script.py ten_file_input.txt", file=sys.stderr)
        sys.exit(1)

    input_file = sys.argv[1]

    output_file = input("Nhập tên file output CSV (ví dụ: ketqua.csv) - bỏ qua nếu không cần lưu: ").strip()
    if not output_file:
        output_file = None

    process_ip_file(input_file, output_file=output_file)