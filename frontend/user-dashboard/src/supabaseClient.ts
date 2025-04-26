import { createClient } from '@supabase/supabase-js';

// Lấy URL và Anon Key từ biến môi trường (phải được định nghĩa trong .env)
// Vite yêu cầu tiền tố VITE_ cho các biến môi trường phía client
const supabaseUrl = import.meta.env.VITE_SUPABASE_URL;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

// Kiểm tra xem các biến môi trường đã được cung cấp chưa
if (!supabaseUrl) {
  console.error('Error: VITE_SUPABASE_URL is not defined in your .env file');
  // Có thể throw error hoặc cung cấp giá trị mặc định không hoạt động
  // throw new Error('VITE_SUPABASE_URL is not defined');
}

if (!supabaseAnonKey) {
  console.error('Error: VITE_SUPABASE_ANON_KEY is not defined in your .env file');
  // throw new Error('VITE_SUPABASE_ANON_KEY is not defined');
}

// Khởi tạo và export Supabase client
// Chỉ khởi tạo nếu cả hai biến đều tồn tại để tránh lỗi runtime
export const supabase = (supabaseUrl && supabaseAnonKey)
  ? createClient(supabaseUrl, supabaseAnonKey)
  : null; // Hoặc một client giả lập/thông báo lỗi

// Log để xác nhận client được tạo (hoặc không)
if (supabase) {
  console.log('Supabase client initialized.');
} else {
  console.error('Supabase client could not be initialized due to missing environment variables.');
}