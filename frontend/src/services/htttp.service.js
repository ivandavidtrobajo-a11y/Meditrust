import Axios from "axios";

const API_URL = import.meta.env.VITE_API_URL;
Axios.defaults.baseURL = API_URL;

export class HttpService {
  _axios = Axios.create();

  addRequestInterceptor = (onFulfilled, onRejected) => {
    this._axios.interceptors.request.use(onFulfilled, onRejected);
  };

  addResponseInterceptor = (onFulfilled, onRejected) => {
    this._axios.interceptors.response.use(onFulfilled, onRejected);
  };

  get = async (url) => await this.request(this.getOptionsConfig("get", url));

  post = async (url, data) => await this.request(this.getOptionsConfig("post", url, data));

  put = async (url, data) => await this.request(this.getOptionsConfig("put", url, data));

  patch = async (url, data) => await this.request(this.getOptionsConfig("patch", url, data));

  delete = async (url) => await this.request(this.getOptionsConfig("delete", url));

  getOptionsConfig = (method, url, data) => {
    return {
      method,
      url,
      data,
      // ✅ withCredentials para JWT en cookies
      withCredentials: true,
      headers: {
        "Content-Type": "application/json",
        "Accept": "application/json",
      },
    };
  };

  request(options) {
    return new Promise((resolve, reject) => {
      this._axios
        .request(options)
        .then((res) => resolve(res.data))
        .catch((ex) => {
          // ✅ SOLUCIÓN: Rechaza el error COMPLETO, no solo .data
          // Antes: reject(ex?.response?.data || { message: ex?.message })
          // Problema: Pierde status y metadata del error
          // Después: reject(errorObject) con status, data, message
          
          const errorObject = {
            // Status HTTP (si la petición llegó al servidor)
            status: ex?.response?.status || null,
            // Datos de error del servidor
            data: ex?.response?.data || null,
            // Mensaje genérico (si no hay respuesta del servidor)
            message: ex?.message || "Network error",
            // Flag para debugging: ¿recibimos respuesta HTTP?
            hasResponse: !!ex?.response,
            // Flag para debugging: ¿se envió la petición?
            hasRequest: !!ex?.request,
          };

          console.error("HTTP Service Error:", errorObject);
          reject(errorObject);
        });
    });
  }
}

export default new HttpService();
