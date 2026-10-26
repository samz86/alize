import React from "react";
import { createRoot } from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import App from "./App.jsx";
import Home from "./pages/Home.jsx";
import Classement from "./pages/Classement.jsx";
import Ville from "./pages/Ville.jsx";
import Articles from "./pages/Articles.jsx";
import Article from "./pages/Article.jsx";
import Quiz from "./pages/Quiz.jsx";
import Simulateur from "./pages/Simulateur.jsx";
import Demarche from "./pages/Demarche.jsx";
import "./styles.css";

const router = createBrowserRouter([
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <Home /> },
      { path: "classement", element: <Classement /> },
      { path: "ville/:slug", element: <Ville /> },
      { path: "articles", element: <Articles /> },
      { path: "articles/:slug", element: <Article /> },
      { path: "quiz", element: <Quiz /> },
      { path: "simulateur", element: <Simulateur /> },
      { path: "demarche", element: <Demarche /> },
    ],
  },
]);

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>
);
