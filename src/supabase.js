import { createClient } from '@supabase/supabase-js';

const SUPABASE_URL = "https://cnkxsxhgdtuxknrzufhv.supabase.co";
const SUPABASE_KEY = "sb_publishable_QEoX_f9G_Gf9kaaDZpaH-g_ageY5WFK";

export const supabase = createClient(SUPABASE_URL, SUPABASE_KEY);
