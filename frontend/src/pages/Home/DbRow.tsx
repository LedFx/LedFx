import { Stack, Typography } from '@mui/material'

const DbRow = ({
  left,
  right
}: {
  left: string | undefined
  right: string | number | undefined
}) => {
  return (
    <Stack
      direction="row"
      width="100%"
      justifyContent="space-between"
      alignItems="center"
    >
      <Typography variant="body1">{left}</Typography>
      <Typography>{right}</Typography>
    </Stack>
  )
}

export default DbRow
