import './globals.css';
import type { Metadata } from 'next';
export const metadata:Metadata={title:'FlashyBets | The daily sports book',description:'NHL, NBA and NFL probability boards, game context and results tracking.'};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
