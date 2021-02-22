import React, { useState } from "react";
import { makeStyles } from "@material-ui/core/styles";
import { SketchPicker } from "react-color";
import { GradientPickerPopover } from "react-linear-gradient-picker";

const useStyles = makeStyles({
  picker: {
    position: "relative",
    '& .popover': {
      background: "#fff"
    }
  }
});

const rgbToRgba = (rgb, a = 1) =>
  rgb.replace("rgb(", "rgba(").replace(")", `, ${a})`);

const WrappedSketchPicker = ({ onSelect, ...rest }) => {
  return (
    <SketchPicker
      {...rest}
      color={rgbToRgba(rest.color, rest.opacity)}
      onChange={(c) => {
        const { r, g, b, a } = c.rgb;
        onSelect(`rgb(${r}, ${g}, ${b})`, a);
      }}
    />
  );
};

const initialPallet = [
  { offset: "0.00", color: "rgb(128, 0, 0)" },
  { offset: "1.00", color: "rgb(248, 231, 28)" }
];

export default function GradientCard() {
  const classes = useStyles();
  const [palette, setPalette] = useState(initialPallet);
  const [open, setOpen] = useState(false);
  const [angle, setAngle] = useState(90);

  return (<div className={classes.picker}>
    <GradientPickerPopover
      {...{
        open,
        setOpen,
        angle,
        setAngle,
        showAnglePicker: true,
        width: 220,
        maxStops: 3,
        paletteHeight: 32,
        palette,
        onPaletteChange: setPalette
      }}
    >
      <WrappedSketchPicker />
    </GradientPickerPopover>
  </div>)
}