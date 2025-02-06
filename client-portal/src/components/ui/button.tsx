export const Button = ({ children, onClick }: { children: React.ReactNode; onClick?: () => void }) => (
    <button className="px-4 py-2 bg-blue-500 text-white rounded" onClick={onClick}>
        {children}
    </button>
);
