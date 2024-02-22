import {
  Rotate90DegreesCw,
  Save,
  SwapHoriz,
  SwapVert
} from '@mui/icons-material'
import { Box, Button, Slider, Stack } from '@mui/material'
import { Ledfx } from '../../../../api/ledfx'
import Popover from '../../../../components/Popover/Popover'
import { transpose } from '../../../../utils/helpers'
import { MCell } from './M.utils'

const MControls = ({
  rowN,
  colN,
  setRowNumber,
  setColNumber,
  virtual,
  m,
  setM
}: any) => {
  return (
    <>
      <Stack direction="row" width={500} justifyContent="space-between">
        Rows:
        <Box width={400}>
          <Slider
            min={1}
            max={50}
            value={rowN}
            onChange={(e, newRowNumber) =>
              typeof newRowNumber === 'number' && setRowNumber(newRowNumber)
            }
          />
        </Box>
        {rowN}
      </Stack>
      <Stack direction="row" width={500} justifyContent="space-between">
        Columns:
        <Box width={400}>
          <Slider
            min={1}
            max={50}
            value={colN}
            onChange={(e, newColNumber) =>
              typeof newColNumber === 'number' && setColNumber(newColNumber)
            }
          />
        </Box>
        {colN}
      </Stack>
      <Stack
        direction="row"
        width={500}
        justifyContent="space-between"
        margin="1rem 0"
      >
        <Stack direction="row" justifyContent="flex-start">
          <Button style={{ marginRight: 8 }} onClick={() => setM(transpose(m))}>
            <Rotate90DegreesCw />
          </Button>
          <Button
            style={{ marginRight: 8 }}
            onClick={() => {
              const toReverse = JSON.parse(JSON.stringify(m))
              setM(toReverse.reverse())
            }}
          >
            <SwapVert />
          </Button>
          <Button
            style={{ marginRight: 32 }}
            onClick={() => {
              const toReverse = JSON.parse(JSON.stringify(m))
              for (let index = 0; index < toReverse.length; index += 1) {
                toReverse[index] = toReverse[index].reverse()
              }
              setM(toReverse)
            }}
          >
            <SwapHoriz />
          </Button>
        </Stack>
        <Stack direction="row" justifyContent="flex-start">
          <Popover
            style={{ marginRight: 8 }}
            color="inherit"
            variant="outlined"
            onConfirm={() => {
              setM(Array(rowN).fill(Array(colN).fill(MCell)))
            }}
          />

          <Button
            onClick={() =>
              Ledfx('/api/virtuals', 'POST', {
                config: {
                  ...virtual.config,
                  rows: rowN
                },
                matrix: m,
                id: virtual.id
              })
            }
            startIcon={<Save />}
          >
            Save
          </Button>
        </Stack>
      </Stack>
    </>
  )
}

export default MControls
