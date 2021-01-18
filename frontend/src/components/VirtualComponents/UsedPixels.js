import React from 'react'
import { ListItemText } from "@material-ui/core";
import { useSelector } from "react-redux";

const UsedPixels = ({ virtual, device }) => {
  const list = useSelector(state => state.virtuals.list)
  const test = list.find(reduxItem => reduxItem.name === virtual).items.find(d => d.id === device.id)
  const pixels = test && test.used_pixel
  return (
    <ListItemText style={{ flexBasis: "20%", flexGrow: 'unset', width: "20%", textAlign: 'center' }} secondary={'Used Pixels'} primary={pixels}
    />
  )
}

export default UsedPixels
