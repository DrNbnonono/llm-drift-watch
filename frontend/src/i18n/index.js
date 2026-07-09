import i18n from "i18next";
import { initReactI18next } from "react-i18next";

import zhCN from "./zh-CN.js";
import en from "./en.js";

const requested =
  (typeof import.meta !== "undefined" && import.meta.env && import.meta.env.VITE_LANG) ||
  (typeof window !== "undefined" && window.localStorage && window.localStorage.getItem("qb_lang")) ||
  "zh-CN";

const resources = {
  "zh-CN": { translation: zhCN },
  en: { translation: en },
};

i18n
  .use(initReactI18next)
  .init({
    resources,
    lng: requested in resources ? requested : "zh-CN",
    fallbackLng: "zh-CN",
    interpolation: {
      escapeValue: false,
    },
    returnEmptyString: false,
  });

export default i18n;
