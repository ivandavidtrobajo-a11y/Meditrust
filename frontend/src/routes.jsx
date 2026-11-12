
import Dashboard from "layouts/dashboard";
import Medistrust from "layouts/Medistrust";




import Smartwatch from "layouts/smartwatch";
import PatientCapture from "layouts/patient-capture";
import DoctorDashboard from "layouts/doctor-dashboard";
import PatientDashboard from "layouts/patient-dashboard";
import SignIn from "layouts/authentication/sign-in";
import SignUp from "layouts/authentication/sign-up";

import UserManagement from "layouts/user-management";

import Login from "auth/login";
import Register from "auth/register";
import ForgotPassword from "auth/forgot-password";
import ResetPassword from "auth/reset-password";

// @mui icons
import Icon from "@mui/material/Icon";

const routes = [
  {
    type: "collapse", name: "Panel médico", key: "doctor-dashboard",
    icon: <Icon fontSize="small">medical_services</Icon>, route: "/doctor-dashboard",
    allowedRoles: ["medico"], component: <DoctorDashboard />,
  },
  {
    type: "collapse", name: "Mi embarazo", key: "patient-dashboard",
    icon: <Icon fontSize="small">pregnant_woman</Icon>, route: "/patient-dashboard",
    allowedRoles: ["embarazada"], component: <PatientDashboard />,
  },
  {
    type: "collapse",
    name: "Inicio",
    key: "dashboard",
    icon: <Icon fontSize="small">dashboard</Icon>,
    route: "/dashboard",
    allowedRoles: ["medico", "admin"],
    component: <Dashboard />,
  },
  {
    type: "collapse",
    name: "MedisTrust",
    key: "Medistrust",
    icon: <Icon fontSize="small">IA</Icon>,
    route: "/Medistrust",
    allowedRoles: ["medico"],
    component: <Medistrust />,
  },

{
  type: "collapse",
  name: "Captura de pacientes",
  key: "patient-capture",
  icon: <Icon fontSize="small">cloud_upload</Icon>,
  route: "/patient-capture",
  allowedRoles: ["embarazada"],
  component: <PatientCapture />,
},
{
  type: "collapse",
  name: "Smartwatch",
  key: "smartwatch",
  icon: <Icon fontSize="small">watch</Icon>,
  route: "/smartwatch",
  allowedRoles: [],
  component: <Smartwatch />,
},

  {
    type: "examples",
    name: "Gestionar Usuarios",
    icon: <Icon fontSize="small">list</Icon>,
    route: "/user-management",
    allowedRoles: ["admin"],
    component: <UserManagement />,
  },

  {
    type: "auth",
    name: "Login",
    key: "login",
    icon: <Icon fontSize="small">login</Icon>,
    route: "/auth/login",
    component: <Login />,
  },
  {
    type: "auth",
    name: "Register",
    key: "register",
    icon: <Icon fontSize="small">reigster</Icon>,
    route: "/auth/register",
    component: <Register />,
  },
  {
    type: "auth",
    name: "Olvide mi Contraseña",
    key: "forgot-password",
    icon: <Icon fontSize="small">assignment</Icon>,
    route: "/auth/forgot-password",
    component: <ForgotPassword />,
  },
  {
    type: "auth",
    name: "Resetiar Contraseña",
    key: "reset-password",
    icon: <Icon fontSize="small">assignment</Icon>,
    route: "/auth/reset-password",
    component: <ResetPassword />,
  },
];

export default routes;
