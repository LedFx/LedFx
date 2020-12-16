import React, { useState, useEffect } from 'react';
import { useDispatch, useSelector } from "react-redux";
import { DragDropContext, Droppable } from 'react-beautiful-dnd';
import { List } from "@material-ui/core";
import RootRef from "@material-ui/core/RootRef";
import DragDropItem from "./DragDropItem"

const reorder = (list, startIndex, endIndex) => {
    const result = Array.from(list);
    const [removed] = result.splice(startIndex, 1);
    result.splice(endIndex, 0, removed);

    return result;
};

const DragDropContainer = React.memo(function DragDropContainer({ listItems, provided, style, virtual, device }) {
    const dispatch = useDispatch()
    const onDeleteVitem = () => {
        dispatch({ type: 'virtuals/DELETE_SEGMENT', payload: { virtual: virtual, device: device } })
    }
    return (<List style={style}>
        {listItems.map((listItem, index) => (
            <DragDropItem
                virtual={virtual}
                listItem={listItem}
                index={index}
                key={`${listItem.id}-${index}`}
                onDeleteVitem={onDeleteVitem}
                style={{ marginBottom: '5em' }}
            />
        ))}
        {provided.placeholder}
    </List>)
});

export default function DragDropWrapper({
    items,
    virtual,
    device,
    setdeviceListYz
}) {
    const [state, setState] = useState({ listitems: items.sort((a, b) => a.order_number > b.order_number ? 1 : -1) });
    const dispatch = useDispatch();
    const virtuals = useSelector(state => state.virtuals.list)
    function onDragEnd(result) {
        if (!result.destination) {
            // console.log("NO DESTINATION")
            return;
        }
        if (result.destination.index === result.source.index) {
            // console.log("START=STOP",)
            return;
        }
        const listitems = reorder(state.listitems, result.source.index, result.destination.index);
        listitems.map((item, index) => {
            const [vir] = virtuals.map(v => v.items.find(vi => vi.id === item.id))
            vir.order_number = index

            return dispatch({ type: 'virtuals/CHANGE_SEGMENT', payload: { virtual: virtual, device: { id: vir.id }, newValue: vir } })
        })
        setState({ listitems });
    }

    useEffect(() => {
        setState({ listitems: items })

    }, [items])

    return (
        <DragDropContext onDragEnd={onDragEnd}>
            <Droppable droppableId="list">
                {(provided, snapshot) => (
                    <RootRef rootRef={provided.innerRef}>
                        <DragDropContainer listItems={state.listitems} provided={provided} virtual={virtual.name} device={device} setdeviceListYz={setdeviceListYz} />
                    </RootRef>
                )}
            </Droppable>
        </DragDropContext>
    );
}
