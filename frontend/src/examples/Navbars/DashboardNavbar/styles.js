function navbar(theme, ownerState) {
  const { palette, boxShadows, functions, transitions, breakpoints, borders } = theme;
  const { transparentNavbar, absolute, light, darkMode } = ownerState;
  const { dark, white, text, transparent, background } = palette;
  const { navbarBoxShadow } = boxShadows;
  const { rgba, pxToRem } = functions;
  const { borderRadius } = borders;

  return {
    boxShadow: transparentNavbar || absolute ? "none" : navbarBoxShadow,
    backdropFilter: transparentNavbar || absolute ? "none" : `saturate(180%) blur(${pxToRem(24)})`,
    backgroundColor: transparentNavbar || absolute
      ? `${transparent.main} !important`
      : rgba(darkMode ? background.default : white.main, 0.92),
    color: light ? white.main : transparentNavbar ? text.main : dark.main,
    top: absolute ? 0 : pxToRem(8),
    minHeight: pxToRem(64),
    display: "grid",
    alignItems: "center",
    borderRadius: 0,
    paddingTop: pxToRem(4),
    paddingBottom: pxToRem(4),
    paddingRight: absolute ? pxToRem(8) : 0,
    paddingLeft: absolute ? pxToRem(12) : 0,
    "& > *": {
      transition: transitions.create("all", {
        easing: transitions.easing.easeInOut,
        duration: transitions.duration.standard,
      }),
    },
    "& .MuiToolbar-root": {
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      minHeight: "auto",
      padding: `${pxToRem(4)} ${pxToRem(8)}`,
      [breakpoints.up("sm")]: { padding: `${pxToRem(4)} ${pxToRem(16)}` },
    },
    [breakpoints.up("md")]: { borderRadius: borderRadius.xl },
  };
}

const navbarContainer = ({ breakpoints }) => ({
  flexDirection: "row",
  alignItems: "center",
  justifyContent: "space-between",
  pt: 0.5,
  pb: 0.5,
  minWidth: 0,
  [breakpoints.up("md")]: { paddingTop: 0, paddingBottom: 0 },
});

const navbarRow = ({ breakpoints }, { isMini }) => ({
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  minWidth: 0,
  width: "100%",
  [breakpoints.up("md")]: {
    justifyContent: isMini ? "space-between" : "stretch",
    width: isMini ? "100%" : "max-content",
  },
  [breakpoints.up("xl")]: { justifyContent: "stretch !important", width: "max-content !important" },
});

const navbarIconButton = ({ typography: { size }, breakpoints }) => ({
  px: { xs: 0.5, sm: 1 },
  "& .material-icons, .material-icons-round": { fontSize: `${size.xl} !important` },
  "& .MuiTypography-root": {
    display: "none",
    [breakpoints.up("sm")]: { display: "inline-block", lineHeight: 1.2, ml: 0.5 },
  },
});

const navbarMobileMenu = ({ breakpoints }) => ({
  display: "inline-flex",
  lineHeight: 0,
  [breakpoints.up("xl")]: { display: "none" },
});

export { navbar, navbarContainer, navbarRow, navbarIconButton, navbarMobileMenu };
