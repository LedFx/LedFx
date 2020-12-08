import React, { useState, useEffect } from 'react';
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

const UsedPixels = ({ config, listItem, pixel_count }) => {
    const [pixelsyz, setpixelsyz] = useState({})

    useEffect(() => {
        setpixelsyz(config)
    }, [config])
    return (
        <ListItemText style={{ flexBasis: "20%", flexGrow: 'unset', width: "20%", textAlign: 'center' }} secondary={'Used Pixels'} primary={(pixelsyz[listItem.yz] && (pixelsyz[listItem.yz].led_end - pixelsyz[listItem.yz].led_start)) || pixel_count}
        />
    )
}
// listItem: config
// index: ordering
const DndListItem = ({ listItem, index, config, setconfig, totalPixel, settotalPixel }) => {
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
                        <ReorderIcon />
                    </ListItemIcon>
                    <ListItemText
                        primary={listItem.name}
                        secondary={listItem.config.ip_address}
                        style={{ flexBasis: "30%", flexGrow: 'unset', width: "30%" }}
                    />
                    <ListItemText style={{ flexBasis: "20%", flexGrow: 'unset', width: "20%" }}>
                        <PixelSlider totalPixel={totalPixel} settotalPixel={settotalPixel} pixel_count={listItem.config.pixel_count} setconfig={setconfig} config={config} yz={listItem.yz} listItem={listItem} />
                    </ListItemText>
                    <UsedPixels config={config} pixel_count={listItem.config.pixel_count} setconfig={setconfig} listItem={listItem} />
                    <ListItemSecondaryAction>

                        <IconButton onClick={() => {
                            console.log("DELETING", listItem)
                        }}>
                            <DeleteIcon />
                        </IconButton>
                    </ListItemSecondaryAction>
                </ListItem>
            )}
        </Draggable>
    )
};

const DndListContainer = React.memo(function DndListContainer({ listItems, provided, style, config, setconfig, totalPixel, settotalPixel }) {

    return (<List style={style}>
        {listItems.map((listItem, index) => (
            <DndListItem
                listItem={listItem}
                index={index}
                key={`${listItem.id}-${index}`}
                config={config}
                setconfig={setconfig}
                totalPixel={totalPixel}
                settotalPixel={settotalPixel}
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
    setconfig,
    totalPixel,
    settotalPixel
}) {

    const [state, setState] = useState({ listitems: items });
    console.log("DAMN", items, " AND ", state)
    function onDragEnd(result) {
        if (!result.destination) {
            console.log("NO DESTINATION")
            return;
        }

        if (result.destination.index === result.source.index) {
            console.log("START=STOP",)
            return;
        }

        const listitems = reorder(state.listitems, result.source.index, result.destination.index);
        console.log("Reordered", listitems)
        setState({ listitems });
    }



    const getListStyle = isDraggingOver => ({
        //background: isDraggingOver ? 'lightblue' : 'lightgrey',
    });

    useEffect(() => {
        setState({ listitems: items })

    }, [items])

    return (
        <DragDropContext onDragEnd={onDragEnd}>
            <Droppable droppableId="list">
                {(provided, snapshot) => console.log(state) || (
                    <RootRef rootRef={provided.innerRef}>
                        <DndListContainer style={getListStyle(snapshot.isDraggingOver)} totalPixel={totalPixel} settotalPixel={settotalPixel} listItems={state.listitems} provided={provided} config={config} setconfig={setconfig} />
                    </RootRef>
                )}
            </Droppable>
        </DragDropContext>
    );
}
