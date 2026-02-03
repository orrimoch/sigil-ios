import Foundation

/// F3.2: Daily Quote
/// 50+ quotes for app launch, random selection
struct DailyQuote {
    let text: String
    let author: String
    
    /// Get a random quote for today (consistent throughout the day)
    static func today() -> DailyQuote {
        let calendar = Calendar.current
        let dayOfYear = calendar.ordinality(of: .day, in: .year, for: Date()) ?? 1
        let index = dayOfYear % quotes.count
        return quotes[index]
    }
    
    /// Get a completely random quote
    static func random() -> DailyQuote {
        quotes.randomElement() ?? quotes[0]
    }
    
    // MARK: - Quotes Collection (50+)
    
    static let quotes: [DailyQuote] = [
        // Warren Buffett
        DailyQuote(text: "The stock market is a device for transferring money from the impatient to the patient.", author: "Warren Buffett"),
        DailyQuote(text: "Be fearful when others are greedy, and greedy when others are fearful.", author: "Warren Buffett"),
        DailyQuote(text: "Price is what you pay. Value is what you get.", author: "Warren Buffett"),
        DailyQuote(text: "Risk comes from not knowing what you're doing.", author: "Warren Buffett"),
        DailyQuote(text: "The best investment you can make is in yourself.", author: "Warren Buffett"),
        DailyQuote(text: "Never invest in a business you cannot understand.", author: "Warren Buffett"),
        DailyQuote(text: "Our favorite holding period is forever.", author: "Warren Buffett"),
        
        // Charlie Munger
        DailyQuote(text: "The big money is not in the buying and selling, but in the waiting.", author: "Charlie Munger"),
        DailyQuote(text: "Knowing what you don't know is more useful than being brilliant.", author: "Charlie Munger"),
        DailyQuote(text: "In my whole life, I have known no wise people who didn't read all the time.", author: "Charlie Munger"),
        
        // Peter Lynch
        DailyQuote(text: "Know what you own, and know why you own it.", author: "Peter Lynch"),
        DailyQuote(text: "The stock market is filled with individuals who know the price of everything, but the value of nothing.", author: "Peter Lynch"),
        DailyQuote(text: "Go for a business that any idiot can run – because sooner or later, any idiot is probably going to run it.", author: "Peter Lynch"),
        DailyQuote(text: "Everyone has the brainpower to make money in stocks. Not everyone has the stomach.", author: "Peter Lynch"),
        
        // Benjamin Graham
        DailyQuote(text: "The intelligent investor is a realist who sells to optimists and buys from pessimists.", author: "Benjamin Graham"),
        DailyQuote(text: "In the short run, the market is a voting machine. In the long run, it is a weighing machine.", author: "Benjamin Graham"),
        DailyQuote(text: "The investor's chief problem – and even his worst enemy – is likely to be himself.", author: "Benjamin Graham"),
        DailyQuote(text: "Buy not on optimism, but on arithmetic.", author: "Benjamin Graham"),
        
        // John Templeton
        DailyQuote(text: "The four most dangerous words in investing are: 'This time it's different.'", author: "John Templeton"),
        DailyQuote(text: "Bull markets are born on pessimism, grow on skepticism, mature on optimism, and die on euphoria.", author: "John Templeton"),
        
        // Ray Dalio
        DailyQuote(text: "He who lives by the crystal ball will eat shattered glass.", author: "Ray Dalio"),
        DailyQuote(text: "Diversifying well is the most important thing you need to do in order to invest well.", author: "Ray Dalio"),
        DailyQuote(text: "Pain + Reflection = Progress.", author: "Ray Dalio"),
        
        // Howard Marks
        DailyQuote(text: "You can't predict. You can prepare.", author: "Howard Marks"),
        DailyQuote(text: "The biggest investing errors come not from factors that are informational or analytical, but from those that are psychological.", author: "Howard Marks"),
        DailyQuote(text: "There's no single best investment. What matters is how well all your investments work together.", author: "Howard Marks"),
        
        // Jesse Livermore
        DailyQuote(text: "The market does not beat them. They beat themselves.", author: "Jesse Livermore"),
        DailyQuote(text: "There is nothing new on Wall Street. What has happened before will happen again.", author: "Jesse Livermore"),
        DailyQuote(text: "Money is made by sitting, not trading.", author: "Jesse Livermore"),
        
        // George Soros
        DailyQuote(text: "It's not whether you're right or wrong, but how much money you make when you're right.", author: "George Soros"),
        DailyQuote(text: "Markets are constantly in a state of uncertainty and flux.", author: "George Soros"),
        
        // John Bogle
        DailyQuote(text: "Time is your friend; impulse is your enemy.", author: "John Bogle"),
        DailyQuote(text: "Don't look for the needle in the haystack. Just buy the haystack.", author: "John Bogle"),
        DailyQuote(text: "The stock market is a giant distraction to the business of investing.", author: "John Bogle"),
        
        // Seth Klarman
        DailyQuote(text: "The stock market is the story of cycles and of the human behavior that is responsible for overreactions.", author: "Seth Klarman"),
        DailyQuote(text: "Value investing is at its core the marriage of a contrarian streak and a calculator.", author: "Seth Klarman"),
        
        // Philip Fisher
        DailyQuote(text: "The stock market is filled with individuals who know the price of everything, but the value of nothing.", author: "Philip Fisher"),
        DailyQuote(text: "I don't want a lot of good investments; I want a few outstanding ones.", author: "Philip Fisher"),
        
        // William O'Neil
        DailyQuote(text: "What seems too high and risky to the majority generally goes higher.", author: "William O'Neil"),
        DailyQuote(text: "The whole secret to winning big in the stock market is not to be right all the time, but to lose the least amount possible when you're wrong.", author: "William O'Neil"),
        
        // Paul Tudor Jones
        DailyQuote(text: "The secret to being successful from a trading perspective is to have an indefatigable thirst for information and knowledge.", author: "Paul Tudor Jones"),
        DailyQuote(text: "Don't be a hero. Don't have an ego.", author: "Paul Tudor Jones"),
        
        // Carl Icahn
        DailyQuote(text: "In life and business, there are two cardinal sins. The first is to act precipitously without thought and the second is to not act at all.", author: "Carl Icahn"),
        
        // Mark Cuban
        DailyQuote(text: "It doesn't matter how many times you fail. You only have to be right once.", author: "Mark Cuban"),
        
        // Naval Ravikant
        DailyQuote(text: "Seek wealth, not money or status. Wealth is having assets that earn while you sleep.", author: "Naval Ravikant"),
        DailyQuote(text: "Play long-term games with long-term people.", author: "Naval Ravikant"),
        
        // Morgan Housel
        DailyQuote(text: "Getting money requires taking risks, being optimistic, and putting yourself out there. Keeping money requires humility and fear.", author: "Morgan Housel"),
        DailyQuote(text: "Doing well with money has little to do with how smart you are and a lot to do with how you behave.", author: "Morgan Housel"),
        
        // General Wisdom
        DailyQuote(text: "Compound interest is the eighth wonder of the world.", author: "Albert Einstein (attributed)"),
        DailyQuote(text: "An investment in knowledge pays the best interest.", author: "Benjamin Franklin"),
        DailyQuote(text: "Rule No. 1: Never lose money. Rule No. 2: Never forget rule No. 1.", author: "Warren Buffett"),
    ]
}
