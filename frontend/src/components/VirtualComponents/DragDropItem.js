import React from 'react'
import { useDispatch } from "react-redux";
import {
  ListItem,
  ListItemText,
  ListItemIcon,
  ListItemSecondaryAction
} from "@material-ui/core";
import { Draggable } from 'react-beautiful-dnd';
import FormatLineSpacingIcon from '@material-ui/icons/FormatLineSpacing';
import PixelSlider from './PixelSlider';
import PopoverSure from './PopoverSure';
import UsedPixels from './UsedPixels'

const DragDropItem = ({ listItem, virtual, index }) => {
  const dispatch = useDispatch()
  const onDeleteVitem = () => {
    dispatch({ type: 'virtuals/DELETE_SEGMENT', payload: { virtual: virtual, device: listItem } })
  }

  const getItemStyle = (isDragging, draggableStyle) => ({
    // styles we need to apply on draggables
    ...draggableStyle,
    borderTop: "1px dashed grey",
    borderBottom: "1px dashed grey",
    ...(isDragging && {
      background: "rgb(235,235,235)"
    })
  });

  return (
    <Draggable key={`${listItem.id}-${index}`} draggableId={listItem.id} index={index} style={{ border: "2px solid red" }}>
      {(provided, snapshot) => (
        <ListItem
          ContainerComponent="li"
          ContainerProps={{ ref: provided.innerRef }}
          {...provided.draggableProps}
          style={getItemStyle(
            snapshot.isDragging,
            provided.draggableProps.style
          )}
        >
          <ListItemIcon  {...provided.dragHandleProps}>
            <FormatLineSpacingIcon color="secondary" />
          </ListItemIcon>
          <ListItemText
            primary={listItem.name}
            secondary={listItem.config.ip_address}
            style={{ flexBasis: "30%", flexGrow: 'unset', width: "30%" }}
          />
          <ListItemText style={{ flexBasis: "20%", flexGrow: 'unset', width: "20%" }}>
            <PixelSlider virtual={virtual} device={listItem} />
          </ListItemText>
          <UsedPixels virtual={virtual} device={listItem} />
          <ListItemSecondaryAction>
            <PopoverSure onDeleteVitem={onDeleteVitem} listItem={listItem} />
          </ListItemSecondaryAction>
        </ListItem>
      )}
    </Draggable>
  )
};

export default DragDropItem
