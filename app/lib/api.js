import axios from "axios";

// replace with your IPv4 from ipconfig
export const API = axios.create({ baseURL: "http://192.168.1.34:8000" });
