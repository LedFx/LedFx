import React, { useState, useEffect } from 'react';
import { DragDropContext, Droppable, Draggable } from 'react-beautiful-dnd';
import {
    List,
    ListItem,
    ListItemText,
    ListItemIcon,
    ListItemSecondaryAction
} from "@material-ui/core";
import RootRef from "@material-ui/core/RootRef";
import ReorderIcon from '@material-ui/icons/Reorder';
import PixelSlider from 'components/PixelSlider';
import PopoverSure from './PopoverSure';

const reorder = (list, startIndex, endIndex) => {
    const result = Array.from(list);
    const [removed] = result.splice(startIndex, 1);
    result.splice(endIndex, 0, removed);

    return result;
};

const UsedPixels = ({ config, listItem, pixel_count }) => {

    return (
        <ListItemText style={{ flexBasis: "20%", flexGrow: 'unset', width: "20%", textAlign: 'center' }} secondary={'Used Pixels'} primary={(config[listItem.yz] && (config[listItem.yz].led_end - config[listItem.yz].led_start)) || pixel_count}
        />
    )
}
// listItem: config
// index: ordering
const DndListItem = ({ listItem, index, config, setconfig, onDeleteVitem }) => {
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
                        <ReorderIcon />
                    </ListItemIcon>
                    <ListItemText
                        primary={listItem.name}
                        secondary={listItem.config.ip_address}
                        style={{ flexBasis: "30%", flexGrow: 'unset', width: "30%" }}
                    />
                    <ListItemText style={{ flexBasis: "20%", flexGrow: 'unset', width: "20%" }}>
                        <PixelSlider pixel_count={listItem.config.pixel_count} setconfig={setconfig} config={config} yz={listItem.yz} />
                    </ListItemText>
                    <UsedPixels config={config} pixel_count={listItem.config.pixel_count} listItem={listItem} />
                    <ListItemSecondaryAction>
                        <PopoverSure onDeleteVitem={onDeleteVitem} listItem={listItem} />
                    </ListItemSecondaryAction>
                </ListItem>
            )}
        </Draggable>
    )
};

const DndListContainer = React.memo(function DndListContainer({ listItems, provided, style, config, setconfig, setdeviceListYz }) {

    const onDeleteVitem = (props) => {
        console.log("DELETING", props.yz, " FROM ", listItems, " Found: ", listItems.find(l => l.yz === props.yz))
        const newlis = [...listItems]
        setdeviceListYz(newlis.filter(l => l.yz !== props.yz))
    }
    return (<List style={style}>
        {listItems.map((listItem, index) => (
            <DndListItem
                listItem={listItem}
                index={index}
                key={`${listItem.id}-${index}`}
                config={config}
                setconfig={setconfig}
                onDeleteVitem={onDeleteVitem}
                style={{ marginBottom: '5em' }}
            />
        ))}
        {provided.placeholder}
    </List>)
});

export default function DndList({
    items,
    config,
    setconfig,
    setdeviceListYz
}) {

    const [state, setState] = useState({ listitems: items });

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
        // background: isDraggingOver ? 'lightblue' : 'lightgrey',
    });

    useEffect(() => {
        setState({ listitems: items })

    }, [items])

    return (
        <DragDropContext onDragEnd={onDragEnd}>
            <Droppable droppableId="list">
                {(provided, snapshot) => (
                    <RootRef rootRef={provided.innerRef}>
                        <DndListContainer style={getListStyle(snapshot.isDraggingOver)} listItems={state.listitems} provided={provided} config={config} setconfig={setconfig} setdeviceListYz={setdeviceListYz} />
                    </RootRef>
                )}
            </Droppable>
        </DragDropContext>
    );
}
