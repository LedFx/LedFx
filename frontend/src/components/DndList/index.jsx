import React, { useState } from 'react';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import {
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    IconButton,
    ListItemSecondaryAction
} from "@material-ui/core";
import RootRef from "@material-ui/core/RootRef";
import DeleteIcon from "@material-ui/icons/Delete";
import ReorderIcon from '@material-ui/icons/Reorder';
import PixelSlider from 'components/PixelSlider';

const reorder = (list, startIndex, endIndex) => {
    const result = Array.from(list);
    const [removed] = result.splice(startIndex, 1);
    result.splice(endIndex, 0, removed);

    return result;
};

// listItem: config
// index: ordering
const DndListItem = ({ listItem, index, config, setconfig }) => {
    const getItemStyle = (isDragging, draggableStyle) => ({
        // styles we need to apply on draggables
        ...draggableStyle,
        padding: "3em 0px 1em 0",
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
                        {index}
                        <ReorderIcon />
                    </ListItemIcon>
                    <ListItemText
                        primary={listItem.name}
                        secondary={listItem.config.ip_address}
                        style={{ flexBasis: "30%", flexGrow: 'unset', width: "30%" }}
                    />
                    <ListItemText style={{ flexBasis: "20%", flexGrow: 'unset', width: "20%" }}>
                        <PixelSlider pixel_count={listItem.config.pixel_count} setconfig={setconfig} config={config} yz={listItem.yz} listItem={listItem} />
                    </ListItemText>
                    <ListItemText style={{ flexBasis: "20%", flexGrow: 'unset', width: "20%", textAlign: 'center' }} secondary={'Used Pixels'} primary={JSON.stringify(config[listItem.yz] && config[listItem.yz].pixels)}>

                    </ListItemText>
                    <ListItemSecondaryAction>

                        <IconButton>
                            <DeleteIcon />
                        </IconButton>
                    </ListItemSecondaryAction>
                </ListItem>
            )}
        </Draggable>
    )
};

const DndListContainer = React.memo(function DndListContainer({ listItems, provided, style, config, setconfig }) {

    return (<List style={style}>
        {listItems.map((listItem, index) => (
            <DndListItem
                listItem={listItem}
                index={index}
                key={`${listItem.id}-${index}`}
                config={config}
                setconfig={setconfig}
                style={{ marginBottom: '5em' }}
            // EMIN YEON

            />
        ))}
        {provided.placeholder}
    </List>)
});

export default function DndList({
    items,
    config,
    setconfig
}) {
    console.log("DAMN", items)
    const [state, setState] = useState({ listItems: items });

    function onDragEnd(result) {
        if (!result.destination) {
            console.log("NO DESTINATION")
            return;
        }

        if (result.destination.index === result.source.index) {
            console.log("START=STOP")
            return;
        }

        const listItems = reorder(state.listItems, result.source.index, result.destination.index);
        console.log("Reordered", listItems)
        setState(listItems, ...items);
    }



    const getListStyle = isDraggingOver => ({
        //background: isDraggingOver ? 'lightblue' : 'lightgrey',
    });


    return (
        <DragDropContext onDragEnd={onDragEnd}>
            <Droppable droppableId="list">
                {(provided, snapshot) => console.log(state) || (
                    <RootRef rootRef={provided.innerRef}>
                        <DndListContainer style={getListStyle(snapshot.isDraggingOver)} listItems={items} provided={provided} config={config} setconfig={setconfig} />
                    </RootRef>
                )}
            </Droppable>
        </DragDropContext>
    );
}
