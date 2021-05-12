import React from "react";
import { makeStyles } from "@material-ui/core/styles";
import Slider from "@material-ui/core/Slider";
import IconButton from "@material-ui/core/IconButton";
import Play from "@material-ui/icons/PlayArrow";
import RefreshIcon from "@material-ui/icons/Refresh";
import { ColorPicker } from "./ColorPicker.js";
import InputLabel from "@material-ui/core/InputLabel";
import MenuItem from "@material-ui/core/MenuItem";
import FormControl from "@material-ui/core/FormControl";
import Select from "@material-ui/core/Select";
import { TransitionGroup } from 'react-transition-group';

// const ReactCSSTransitionGroup = "react.addons.CSSTransitionGroup";

const useStyles = makeStyles({
  root: {
    width: 250,
    palette: {
      primary: {
        main: "#800000"
      },
      secondary: {
        main: "#0dbedc"
      }
    },
    '& .swatch': {
      width: '28px',
      height: '28px',
      borderRadius: '8px',
      border: '3px solid #fff',
      boxShadow: '0 0 0 1px rgba(0, 0, 0, 0.1), inset 0 0 0 1px rgba(0, 0, 0, 0.1)',
      cursor: 'pointer',
    },
    '& .popover': {
      position: 'absolute',
      top: '0',
      left: 0,
      borderRadius: '9px',
      boxShadow: '0 6px 12px rgba(0, 0, 0, 0.15)',
    }
  },
  input: {
    width: 42
  },
  busterCards: {
    height: "30px",
    borderRadius: "5px",
    border: "2px solid black",
    width: "30px",
    flex: "0 0 30px",
    marginRight: "10px"
  },
  wrapper: {
    display: "flex",
    width: "100vw",
    alignItems: "center",
    margin: "10px"
  },
  busterCards2: {
    height: "30px",
    width: "30px",
    borderRadius: "5px",
    border: "2px solid black",
    flex: "0 0 30px",
    marginRight: "10px"
  },
  wrapper2: {
    display: "flex",
    width: "100vw",
    alignItems: "center",
    margin: "10px"
  },
  busterCards3: {
    height: "30px",
    width: "30px",
    borderRadius: "5px",
    border: "2px solid black",
    flex: "0 0 30px",
    marginRight: "10px"
  },
  wrapper3: {
    display: "flex",
    width: "100vw",
    alignItems: "center",
    margin: "10px"
  },
  innerWrapper: {
    width: "170px",
    flex: "0 0 170px",
    display: "flex",
    border: "1px solid black",
    alignItems: "center",
    justifyContent: "space-around",
    marginRight: "20px"
  },
  formControlSelect: {
    width: "170px",
    flex: "0 0 170px",
    margin: "10px 40px 10px 10px"
  },
  transitionWrapper: {
    display: "flex"
  }
});


export default function TransitionCard() {
  const classes = useStyles();
  const value = 15;
  const [color, setColor] = React.useState("#800000");
  const [color2, setColor2] = React.useState("#0dbedc");
  const [color3, setColor3] = React.useState(color);
  const [type, setType] = React.useState("instant");
  const [transitionTime, setTransitionTime] = React.useState(0.75);


  const handleTransition = (type = "instant", data = "") => {
    setColor3(color2);
  };
  const handleReset = (type = "instant", data = "") => {
    setColor3(color);
  };

  const marks = [
    {
      value: 0,
      label: "0s"
    },
    {
      value: 0.5,
      label: "0.5s"
    },
    {
      value: 1,
      label: "1s"
    },
    {
      value: 2,
      label: "2s"
    },
    {
      value: 3,
      label: "3s"
    },
    {
      value: 4,
      label: "4s"
    },
    {
      value: 5,
      label: "5s"
    }
  ];
  return (
    <div className={classes.root}>
      <div>
        Trasition-Showcase:
        <div style={{ display: "flex", width: "50vw" }}>
          <FormControl variant="outlined" className={classes.formControlSelect}>
            <InputLabel id="demo-simple-select-outlined-label">
              Transition Type
            </InputLabel>
            <Select
              labelId="demo-simple-select-outlined-label"
              id="demo-simple-select-outlined"
              value={type}
              onChange={(e) => setType(e.target.value)}
              label="Transition Type"
            >
              <MenuItem value={"instant"}>Instant</MenuItem>
              <MenuItem value={"fade"}>Fade</MenuItem>
              <MenuItem value={"wipe"}>Wipe</MenuItem>
            </Select>
          </FormControl>

          <Slider
            defaultValue={0.75}
            value={transitionTime}
            onChange={(event, value) => setTransitionTime(value)}
            aria-labelledby="discrete-slider-always"
            step={0.05}
            marks={marks}
            min={0}
            max={5}
            disabled={type === "instant"}
            valueLabelDisplay="on"
          />
        </div>
      </div>
      <div className={classes.wrapper}>
        <div className={classes.innerWrapper}>
          Old Color
          <ColorPicker
            color={color}
            onChange={(e) => {
              setColor(e);
              setColor3(e);
            }}
          />
        </div>
        {[...Array(value)].map((e, i) => (
          <div
            className={classes.busterCards}
            style={{ backgroundColor: color }}
            key={i}
          />
        ))}
      </div>
      <div className={classes.wrapper2}>
        <div className={classes.innerWrapper}>
          New Color
          <ColorPicker color={color2} onChange={setColor2} />
        </div>
        {[...Array(value)].map((e, i) => (
          <div
            className={classes.busterCards2}
            style={{ backgroundColor: color2 }}
            key={i}
          />
        ))}
      </div>
      <div className={classes.wrapper3}>
        <div className={classes.innerWrapper}>
          <IconButton
            onClick={() => {
              handleReset();
            }}
          >
            <RefreshIcon />
          </IconButton>
          <IconButton
            onClick={() => {
              handleTransition();
            }}
          >
            <Play />
          </IconButton>
        </div>
        <TransitionGroup
          className={classes.transitionWrapper}
          transitionName="slide-up"
          transitionAppear={true}
        >
          {[...Array(value)].map((e, i) => (
            <div
              className={classes.busterCards3}
              style={{
                backgroundColor: color3,
                transition: `all ${type === "fade" ? 2.6 * transitionTime : 0
                  }s`,
                transitionDelay: `${type === "wipe" ? (i * transitionTime) / value : 0
                  }s`
              }}
              key={i}
            />
          ))}
        </TransitionGroup>
      </div>
    </div>
  );
}
