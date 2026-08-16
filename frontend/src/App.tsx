import { useEffect } from "react";

import { useMe } from "./api/queries/auth";
import { AppRoutes } from "./router";
import { useAuthStore } from "./stores/auth";

/**
 * Аппын үндэс.
 *
 * Router-ыг зурж, нэвтэрсэн хэрэглэгчийн эрх/ээлжийн төлвийг сэргээнэ
 * (хуудас дахин ачаалагдахад localStorage-д хадгалагдсан токеноор).
 */
export function App() {
  const token = useAuthStore((state) => state.token);

  // Токен байвал профайл/эрхийг сервертэй тааруулна.
  useMe(Boolean(token));

  // Хүрэлтийн интерфэйс — хос дарж томруулахыг хаана.
  useEffect(() => {
    const preventGesture = (event: Event): void => event.preventDefault();
    document.addEventListener("gesturestart", preventGesture);
    return () => document.removeEventListener("gesturestart", preventGesture);
  }, []);

  return <AppRoutes />;
}

export default App;
