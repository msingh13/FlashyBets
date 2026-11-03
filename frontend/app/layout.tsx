import './globals.css';
import type { Metadata } from 'next';
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || '';
export const metadata:Metadata={title:'FlashyBets | The daily sports book',description:'NHL, NBA and NFL probability boards, game context and results tracking.',icons:{icon:[{url:`${basePath}/brand/flashybets-logo.png`,type:'image/png'},{url:`${basePath}/brand/favicon.svg`,type:'image/svg+xml',sizes:'any'}],apple:`${basePath}/brand/flashybets-logo.png`}};
export default function Layout({children}:{children:React.ReactNode}){return <html lang="en"><body>{children}</body></html>}
