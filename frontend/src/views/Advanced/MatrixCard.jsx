import React from "react";
import { makeStyles } from "@material-ui/core/styles";
import Grid from "@material-ui/core/Grid";
import Typography from "@material-ui/core/Typography";
import Slider from "@material-ui/core/Slider";
import Input from "@material-ui/core/Input";
import VolumeUp from "@material-ui/icons/Settings";

const useStyles = makeStyles({
  root: {
    width: 250,

  },
  input: {
    width: 42
  },
});

export default function MatrixCard() {
  const classes = useStyles();
  const [value, setValue] = React.useState(50);

  const handleSliderChange = (event, newValue) => {
    setValue(newValue);
  };

  const handleInputChange = (event) => {
    setValue(event.target.value === "" ? "" : Number(event.target.value));
  };

  const handleBlur = () => {
    if (value < 1) {
      setValue(1);
    } else if (value > 50) {
      setValue(50);
    }
  };
  const [value2, setValue2] = React.useState(50);

  const handleSliderChange2 = (event, newValue) => {
    setValue2(newValue);
  };

  const handleInputChange2 = (event) => {
    setValue2(event.target.value === "" ? "" : Number(event.target.value));
  };

  const handleBlur2 = () => {
    if (value2 < 1) {
      setValue2(1);
    } else if (value2 > 50) {
      setValue2(50);
    }
  };

  return (
    <div className={classes.root}>
      <Typography id="input-slider" gutterBottom>
        Total LEDs
      </Typography>
      <Grid container spacing={2} alignItems="center">
        <Grid item>
          <VolumeUp />
        </Grid>
        <Grid item xs>
          <Slider
            value={typeof value === "number" ? value : 1}
            onChange={handleSliderChange}
            aria-labelledby="input-slider"
            max={100}
          />
        </Grid>
        <Grid item>
          <Input
            className={classes.input}
            value={value}
            margin="dense"
            onChange={handleInputChange}
            onBlur={handleBlur}
            inputProps={{
              step: 10,
              min: 0,
              max: 100,
              type: "number",
              "aria-labelledby": "input-slider"
            }}
          />
        </Grid>
      </Grid>
      <Typography id="input-slider" gutterBottom>
        LEDs per row
      </Typography>
      <Grid container spacing={2} alignItems="center">
        <Grid item>
          <VolumeUp />
        </Grid>
        <Grid item xs>
          <Slider
            min={1}
            max={100}
            value={typeof value2 === "number" ? value2 : 1}
            onChange={handleSliderChange2}
            aria-labelledby="input-slider-2"
          />
        </Grid>
        <Grid item>
          <Input
            className={classes.input}
            value={value2}
            margin="dense"
            onChange={handleInputChange2}
            onBlur={handleBlur2}
            inputProps={{
              step: 10,
              min: 0,
              max: 100,
              type: "number",
              "aria-labelledby": "input-slider-2"
            }}
          />
        </Grid>
      </Grid>

      {[...Array(value)].map((e, i) => (
        <>
          {i % value2 === 0 && <br />}
          <span className="busterCards" key={i}>
            ♦
          </span>
        </>
      ))}

    </div>
  );
}
