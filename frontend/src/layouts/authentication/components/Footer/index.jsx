import PropTypes from "prop-types";

// Material Dashboard 2 React base styles
import typography from "assets/theme/base/typography";

function Footer({ light }) {
  const { size } = typography;

  return (
    <footer
      style={{
        position: "relative",
        display: "block",
        flexShrink: 0,
        width: "100%",
        boxSizing: "border-box",
        padding: "1rem",
        textAlign: "center",
        fontSize: size.sm,
        color: light ? "white" : "#333",
      }}
    >
      © {new Date().getFullYear()} Sistema Médico — Todos los derechos reservados
    </footer>
  );
}

Footer.defaultProps = {
  light: false,
};

Footer.propTypes = {
  light: PropTypes.bool,
};

export default Footer;
